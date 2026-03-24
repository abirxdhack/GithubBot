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
        "<html lang='en'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>GitHub Connected</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Plus+Jakarta+Sans:wght@400;600&display=swap' rel='stylesheet'>"
        "<style>"
        ":root{--gold:#FFD700;--cyan:#00FFF5;--purple:#9D4EDD;--bg:#0A0A0F;--card:rgba(22,22,31,0.7)}*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Plus Jakarta Sans',sans-serif;background:var(--bg);color:#fff;height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}.bg span{position:absolute;width:300px;height:300px;border-radius:50%;filter:blur(100px);opacity:.25;animation:float 10s infinite ease-in-out}.bg span:nth-child(1){background:var(--cyan);top:10%;left:10%}.bg span:nth-child(2){background:var(--purple);bottom:10%;right:10%}.bg span:nth-child(3){background:var(--gold);top:50%;left:50%}@keyframes float{0%,100%{transform:translate(0,0)}50%{transform:translate(40px,-40px)}}.card{background:var(--card);border-radius:24px;padding:50px 40px;text-align:center;max-width:420px;width:90%;box-shadow:0 20px 80px rgba(0,0,0,0.8);animation:fadeUp .8s ease}.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:50px;background:rgba(255,255,255,0.05);margin-bottom:20px;font-size:12px;border:1px solid rgba(255,255,255,0.1)}.badge img{height:18px;animation:wave 2s infinite}@keyframes wave{0%,100%{transform:rotate(0)}25%{transform:rotate(10deg)}75%{transform:rotate(-10deg)}}.icon{font-size:60px;margin-bottom:15px;animation:bounce 1.5s infinite}@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}h1{font-family:'Space Grotesk',sans-serif;font-size:28px;background:linear-gradient(135deg,var(--gold),var(--cyan),var(--purple));-webkit-background-clip:text;color:transparent;margin-bottom:10px}#typing{font-size:14px;color:#aaa;min-height:22px}.btn{display:inline-block;margin-top:25px;padding:12px 25px;border-radius:12px;background:linear-gradient(135deg,var(--cyan),var(--purple));color:#000;font-weight:600;text-decoration:none;transition:.3s}.btn:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,255,245,.4)}.dev{margin-top:25px;font-size:13px;color:#777}.dev strong{background:linear-gradient(135deg,var(--gold),var(--cyan));-webkit-background-clip:text;color:transparent}@keyframes fadeUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='bg'><span></span><span></span><span></span></div>"
        "<div class='card'>"
        "<div class='badge'>Crafted by Abir Arafat Chawdhury <img src='https://www.crossed-flag-pins.com/animated-flag-gif/gifs/Bangladesh_240-animated-flag-gifs.gif'></div>"
        "<div class='icon'>🎉</div>"
        "<h1>GitHub Connected</h1>"
        "<div id='typing'>Your GitHub account has been successfully linked. You're ready to receive real-time updates ⚡</div>"
        "<a href='tg://resolve' class='btn'>Return to Telegram 🚀</a>"
        "<div class='dev'>Created by <strong>Abir Arafat Chawdhury 🇧🇩</strong></div>"
        "</div>"
        "</body>"
        "</html>"
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