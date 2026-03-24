import asyncio
import os

from telethon import events

import config
from bot import Irene
from database.store import DataStore
from helpers import LOGGER, send_message, SmartButtons, new_task
from helpers.guard import admin_only, ban_check

_ITEMS_PER_PAGE = 10
_settings_lock  = asyncio.Lock()
_user_session: dict = {}


def _pfx(cmds):
    esc    = "".join(c if c.isalpha() else f"\\{c}" for c in config.COMMAND_PREFIXES)
    joined = "|".join(cmds)
    return rf"^[{esc}]({joined})(?:\s|$)"


def _load_env_vars() -> dict:
    try:
        with open(".env") as f:
            lines = f.readlines()
        variables = {}
        seen = set()
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                key = key.strip()
                if key not in seen:
                    variables[key] = value.strip()
                    seen.add(key)
        return variables
    except Exception as e:
        LOGGER.error(f"Error loading .env vars: {e}")
        return {}


async def _update_env_var(key: str, value: str):
    async with _settings_lock:
        try:
            env_vars = _load_env_vars()
            env_vars[key] = value
            os.environ[key] = value
            with open(".env", "w") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")
            LOGGER.info(f"Updated env var: {key}")
        except Exception as e:
            LOGGER.error(f"Error updating env var {key}: {e}")
            raise


_config_keys = _load_env_vars()


async def _is_admin(user_id: int) -> bool:
    if user_id == config.ADMIN_ID:
        return True
    guards = await DataStore.get().get_guards()
    return user_id in [g["user_id"] for g in guards]


def _build_settings_markup(page: int = 0):
    keys  = list(_config_keys.keys())
    start = page * _ITEMS_PER_PAGE
    end   = start + _ITEMS_PER_PAGE
    curr  = keys[start:end]

    sb = SmartButtons()
    for i in range(0, len(curr), 2):
        sb.button(text=curr[i], callback_data=f"cfg_edit_{curr[i]}")
        if i + 1 < len(curr):
            sb.button(text=curr[i + 1], callback_data=f"cfg_edit_{curr[i + 1]}")

    if page > 0:
        sb.button(text="⬅️ Previous", callback_data=f"cfg_page_{page - 1}", position="footer")
    if end < len(keys):
        sb.button(text="Next ➡️",     callback_data=f"cfg_page_{page + 1}", position="footer")

    sb.button(text="Close ❌", callback_data="cfg_close", position="footer")
    f_cols = 3 if (page > 0 and end < len(keys)) else 2
    return sb.build_menu(b_cols=2, f_cols=f_cols)


@Irene.on(events.NewMessage(pattern=_pfx(["config"])))
@admin_only
@new_task
async def show_settings(event):
    try:
        await send_message(
            event.chat_id,
            "<b>⚙️ Settings — Select a variable to edit 👇</b>",
            parse_mode="html",
            buttons=_build_settings_markup(0),
        )
        LOGGER.info(f"Settings opened by user_id {event.sender_id}")
    except Exception as e:
        LOGGER.error(f"show_settings error: {e}")
        await send_message(event.chat_id, "<b>❌ Failed to display settings!</b>", parse_mode="html")


@Irene.on(events.CallbackQuery(pattern=rb"cfg_page_(\d+)"))
async def paginate_settings(event):
    if not await _is_admin(event.sender_id):
        return
    try:
        page = int(event.data.decode().split("_")[-1])
        await event.edit(
            "<b>⚙️ Settings — Select a variable to edit 👇</b>",
            parse_mode="html",
            buttons=_build_settings_markup(page),
        )
        await event.answer()
    except Exception as e:
        LOGGER.error(f"paginate_settings error: {e}")
        await event.answer("❌ Failed to paginate!", alert=True)


@Irene.on(events.CallbackQuery(pattern=rb"cfg_edit_(.+)"))
async def edit_var(event):
    if not await _is_admin(event.sender_id):
        return
    try:
        var_name = event.data.decode().split("cfg_edit_", 1)[1]
        if var_name not in _config_keys:
            await event.answer("Invalid variable.", alert=True)
            return

        _user_session[event.sender_id] = {"var": var_name, "chat_id": event.chat_id}

        sb = SmartButtons()
        sb.button(text="Cancel ❌", callback_data="cfg_cancel")

        await event.edit(
            f"<b>Editing <code>{var_name}</code>\n\nCurrent value:</b> <code>{_config_keys.get(var_name, 'N/A')}</code>\n\n<b>Send the new value below.</b>",
            parse_mode="html",
            buttons=sb.build_menu(b_cols=1),
        )
    except Exception as e:
        LOGGER.error(f"edit_var error: {e}")
        await event.answer("❌ Failed to start editing!", alert=True)


@Irene.on(events.CallbackQuery(data=b"cfg_cancel"))
async def cancel_edit(event):
    if not await _is_admin(event.sender_id):
        return
    _user_session.pop(event.sender_id, None)
    try:
        await event.edit("<b>Variable Editing Cancelled ❌</b>", parse_mode="html")
        await event.answer()
    except Exception as e:
        LOGGER.error(f"cancel_edit error: {e}")


@Irene.on(events.CallbackQuery(data=b"cfg_close"))
async def close_settings(event):
    if not await _is_admin(event.sender_id):
        return
    try:
        await event.edit("<b>Closed Settings Menu ✅</b>", parse_mode="html")
        await event.answer()
    except Exception as e:
        LOGGER.error(f"close_settings error: {e}")


@Irene.on(events.NewMessage())
@ban_check
async def update_value(event):
    if not event.message or not event.sender_id:
        return
    try:
        from modules.middleware import track
        await track(event.sender_id, event.chat_id)
    except Exception:
        pass
    if event.sender_id not in _user_session:
        return

    session = _user_session.get(event.sender_id)
    if not session or session.get("chat_id") != event.chat_id:
        return
    if not await _is_admin(event.sender_id):
        return

    text = event.message.text or event.message.message
    if not text or not text.strip():
        await send_message(event.chat_id, "<b>Please provide a non-empty value ❌</b>", parse_mode="html")
        return

    var = session["var"]
    val = text.strip()

    try:
        await _update_env_var(var, val)
        _config_keys[var] = val
        _user_session.pop(event.sender_id, None)
        await send_message(
            event.chat_id,
            f"<b><code>{var}</code> successfully updated to <code>{val}</code> ✅</b>",
            parse_mode="html",
        )
        LOGGER.info(f"User {event.sender_id} updated {var} to {val}")
    except Exception as e:
        LOGGER.error(f"update_value error for {var}: {e}")
        await send_message(event.chat_id, "<b>❌ Failed to update variable!</b>", parse_mode="html")