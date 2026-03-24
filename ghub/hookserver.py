import asyncio
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import HTMLResponse

import config
from crypto.vault import unseal
from database.store import DataStore
from ghub.payloads import route_event
from helpers.utils import truncate_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"ok": True, "service": "ghnotifybot"}


@router.get("/auth/callback")
async def oauth_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    code: str = "",
    state: str = "",
):
    if not code or not state:
        logger.warning("OAuth callback missing code or state")
        return Response(content="Missing code or state", status_code=400)

    handle_oauth = getattr(request.app.state, "handle_oauth", None)
    if handle_oauth:
        background_tasks.add_task(handle_oauth, code, state)
        logger.info(f"OAuth callback queued — state={state[:8]}...")
    else:
        logger.error("handle_oauth not set on app.state!")

    return HTMLResponse(
        "<!DOCTYPE html>"
        "<html><head><title>GitHub Notify Bot</title>"
        "<style>body{font-family:sans-serif;text-align:center;padding:60px;background:#f6f8fa}"
        "h2{color:#2ea44f}.card{background:#fff;border-radius:12px;padding:40px;display:inline-block;"
        "box-shadow:0 2px 12px rgba(0,0,0,.1)}</style></head>"
        "<body><div class='card'>"
        "<h2>✅ GitHub Connected!</h2>"
        "<p>Your GitHub account has been linked successfully.</p>"
        "<p>You can now close this tab and return to Telegram.</p>"
        "</div></body></html>"
    )


@router.post("/webhook/{token}")
async def receive_webhook(token: str, request: Request):
    body = await request.body()
    sig  = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        config.HOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        logger.warning("Rejected webhook — bad signature")
        return Response(content="bad signature", status_code=403)

    try:
        chat_id = int(unseal(token))
    except Exception as e:
        logger.warning(f"Failed to unseal webhook token: {e}")
        return Response(content="bad token", status_code=400)

    event_type = request.headers.get("X-GitHub-Event", "")

    try:
        payload = json.loads(body)
    except Exception:
        return Response(content="bad json", status_code=400)

    if event_type == "repository" and payload.get("action") == "renamed":
        changes  = payload.get("changes", {})
        old_part = (changes.get("repository") or {}).get("name", {}).get("from", "")
        ri       = payload.get("repository", {})
        owner    = (ri.get("owner") or {}).get("login", "")
        new_name = ri.get("name", "")
        if old_part and owner and new_name:
            old_full = f"{owner}/{old_part}"
            new_full = f"{owner}/{new_name}"
            if old_full != new_full:
                await DataStore.get().rename_repo(old_full, new_full)

    asyncio.create_task(_deliver(chat_id, event_type, payload))
    return Response(content="ok", status_code=200)


async def _get_target(chat_id: int, payload: dict) -> int:
    try:
        repo_name = ""
        ri = payload.get("repository") or {}
        repo_name = ri.get("full_name") or ri.get("name") or ""
        if repo_name:
            all_chats = await DataStore.get().find_chats_by_repo(repo_name)
            for entry in all_chats:
                if entry["chat_id"] == chat_id and entry.get("peer_id"):
                    return entry["peer_id"]
    except Exception as e:
        logger.warning(f"_get_target error: {e}")
    return chat_id


async def _deliver(chat_id: int, event_type: str, payload: dict):
    try:
        text, markup = route_event(event_type, payload)
        if not text:
            return
        target = await _get_target(chat_id, payload)
        from bot import Irene
        await Irene.send_message(
            target,
            truncate_text(text),
            parse_mode="html",
            buttons=markup,
            link_preview=False,
        )
    except Exception as e:
        logger.error(f"Delivery failed for {event_type} -> chat {chat_id}: {e}")