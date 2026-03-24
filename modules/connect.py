import re

from telethon import events
from telethon.tl.types import User

import config
from bot import Irene
from cache.ttlcache import TTLCache
from crypto.vault import seal, random_token
from database.store import DataStore
from ghub.oauth import build_auth_url, exchange_code
from helpers import LOGGER, send_message, SmartButtons, new_task

_prefixes    = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_connect_pat = re.compile(rf"^[{_prefixes}]connect(?:\s|$)", re.IGNORECASE)
_logout_pat  = re.compile(rf"^[{_prefixes}]logout(?:\s|$)",  re.IGNORECASE)

_state_cache: TTLCache = TTLCache()


def get_state_cache() -> TTLCache:
    return _state_cache


@Irene.on(events.NewMessage(pattern=_connect_pat))
@new_task
async def connect_handler(event):
    chat = await event.get_chat()
    if not isinstance(chat, User):
        await send_message(
            event.chat_id,
            "⚠️ The /connect command can only be used in a <b>private chat</b> with the bot.",
            parse_mode="html",
        )
        return

    state = random_token()
    url   = build_auth_url(state)

    sb = SmartButtons()
    sb.button("🔗 Connect GitHub", url=url)

    msg = await send_message(
        event.chat_id,
        "Click the button below to link your GitHub account.\n\n"
        "This enables automatic webhook setup and actions like approving PRs.\n\n"
        "<i>⏳ Link expires in 10 minutes.</i>",
        parse_mode="html",
        buttons=sb.build_menu(b_cols=1),
    )

    msg_id = msg.id if msg else None
    await _state_cache.put(state, {"tg_id": event.sender_id, "chat_id": event.chat_id, "msg_id": msg_id}, ttl=600)
    LOGGER.info(f"OAuth state created for tg_id={event.sender_id} state={state[:8]}...")


@Irene.on(events.NewMessage(pattern=_logout_pat))
@new_task
async def logout_handler(event):
    store = DataStore.get()
    await store.clear_token(event.sender_id)
    await send_message(event.chat_id, "✅ Logged out successfully. Use /connect to reconnect.")


async def handle_oauth(code: str, state: str):
    LOGGER.info(f"handle_oauth called — state={state[:8]}...")

    entry = await _state_cache.get(state)
    if not entry:
        LOGGER.warning(f"OAuth state not found or expired: state={state[:8]}...")
        return
    await _state_cache.delete(state)
    tg_id   = entry["tg_id"]
    chat_id = entry["chat_id"]
    msg_id  = entry.get("msg_id")
    LOGGER.info(f"State matched → tg_id={tg_id}")

    try:
        raw_token = await exchange_code(code)
        LOGGER.info(f"Token exchanged OK for tg_id={tg_id}")
    except Exception as e:
        LOGGER.error(f"OAuth code exchange FAILED for tg_id={tg_id}: {e}")
        try:
            await Irene.send_message(
                tg_id,
                "❌ <b>GitHub connection failed.</b>\n"
                "Could not exchange authorization code. Please try /connect again.",
                parse_mode="html",
            )
        except Exception:
            pass
        return

    try:
        encrypted = seal(raw_token)
    except Exception as e:
        LOGGER.error(f"Token encryption FAILED for tg_id={tg_id}: {e}")
        return

    try:
        store = DataStore.get()
        await store.save_token(tg_id, encrypted)
        LOGGER.info(f"Token saved to DB for tg_id={tg_id}")
    except Exception as e:
        LOGGER.error(f"Token DB save FAILED for tg_id={tg_id}: {e}")
        try:
            await Irene.send_message(
                tg_id,
                "❌ <b>GitHub connection failed.</b>\n"
                "Database error. Please try /connect again.",
                parse_mode="html",
            )
        except Exception:
            pass
        return

    try:
        from ghub.ghclient import GhApi
        from crypto.vault import unseal as _unseal
        gh_user = ""
        gh_url  = ""
        try:
            _stored = await DataStore.get().get_account(tg_id)
            if _stored and _stored.token_enc:
                _api = GhApi(_unseal(_stored.token_enc))
                _me  = await _api.get_me()
                gh_user = _me.get("login", "")
                gh_url  = _me.get("html_url", f"https://github.com/{gh_user}")
        except Exception as _e:
            LOGGER.warning(f"Could not fetch GitHub username: {_e}")

        if gh_user:
            user_part = f"**Your Username:** [@{gh_user}]({gh_url})"
        else:
            user_part = "**Your Username:** Connected ✅"

        success_text = (
            "**✅ Github Connected Successfully!**\n"
            "**━━━━━━━━━━━━━━━━**\n"
            f"{user_part}\n\n"
            "Your bot is now live with all updates from your GitHub.\n"
            "Share your repos with it using `/addrepo` command to start webhook."
        )
        if msg_id:
            await Irene.edit_message(chat_id, msg_id, success_text, parse_mode="md", buttons=None)
        else:
            await Irene.send_message(chat_id, success_text, parse_mode="md")
        LOGGER.info(f"Success notification sent to tg_id={tg_id}")
    except Exception as e:
        LOGGER.error(f"Success notification FAILED for tg_id={tg_id}: {e}")