import re

from telethon import events

import config
from bot import Irene
from cache.ttlcache import TTLCache
from crypto.vault import unseal
from database.store import DataStore
from ghub.ghclient import GhApi, GhApiError
from helpers import LOGGER, send_message, new_task, clean_download

_prefixes  = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_ctx_cache: TTLCache = TTLCache()


def get_ctx_cache() -> TTLCache:
    return _ctx_cache


async def _get_api(tg_id: int):
    account = await DataStore.get().get_account(tg_id)
    if not account or not account.token_enc:
        return None
    try:
        token = unseal(account.token_enc)
        return GhApi(token)
    except Exception:
        return None


async def _revoke_warn(chat_id: int, tg_id: int):
    await DataStore.get().clear_token(tg_id)
    await send_message(
        chat_id,
        "⚠️ <b>GitHub authentication failed.</b>\n"
        "Your token expired or was revoked. Please /connect again.",
        parse_mode="html",
    )


async def _issue_state_change(event, state: str):
    reply = await event.message.get_reply_message()
    if not reply:
        await send_message(event.chat_id, "Please use this command <b>in reply</b> to a notification.", parse_mode="html")
        return

    key = f"{event.chat_id}:{reply.id}"
    ctx = await _ctx_cache.get(key)
    if not ctx:
        await send_message(event.chat_id, "Context not found. The notification may be too old.")
        return

    api = await _get_api(event.sender_id)
    if not api:
        from ghub.oauth import build_auth_url
        url = build_auth_url("connect")
        await send_message(event.chat_id, f'Please <a href="{url}">connect your GitHub account</a> first.', parse_mode="html")
        return

    try:
        if state == "closed":
            await api.close_issue(ctx.owner, ctx.repo, ctx.num)
        else:
            await api.reopen_issue(ctx.owner, ctx.repo, ctx.num)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _revoke_warn(event.chat_id, event.sender_id)
            return
        await send_message(event.chat_id, f"Failed to update state: {exc.message}")
        return

    label = "closed" if state == "closed" else "reopened"
    await send_message(event.chat_id, f"✅ Issue/PR #{ctx.num} {label}.")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]close(?:\s|$)", re.IGNORECASE)))
@new_task
async def close_handler(event):
    await _issue_state_change(event, "closed")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]reopen(?:\s|$)", re.IGNORECASE)))
@new_task
async def reopen_handler(event):
    await _issue_state_change(event, "open")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]approve(?:\s|$)", re.IGNORECASE)))
@new_task
async def approve_handler(event):
    reply = await event.message.get_reply_message()
    if not reply:
        await send_message(event.chat_id, "Please use this command <b>in reply</b> to a notification.", parse_mode="html")
        return

    key = f"{event.chat_id}:{reply.id}"
    ctx = await _ctx_cache.get(key)
    if not ctx:
        await send_message(event.chat_id, "Context not found. The notification may be too old.")
        return

    if ctx.kind not in ("pr", "pr_review"):
        await send_message(event.chat_id, "This command is only for Pull Requests.")
        return

    api = await _get_api(event.sender_id)
    if not api:
        from ghub.oauth import build_auth_url
        url = build_auth_url("connect")
        await send_message(event.chat_id, f'Please <a href="{url}">connect your GitHub account</a> first.', parse_mode="html")
        return

    try:
        await api.approve_pr(ctx.owner, ctx.repo, ctx.num)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _revoke_warn(event.chat_id, event.sender_id)
            return
        await send_message(event.chat_id, f"Failed to approve: {exc.message}")
        return

    await send_message(event.chat_id, f"✅ PR #{ctx.num} approved.")
