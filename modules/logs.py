import asyncio
import os
from datetime import datetime

from telethon import events

import config
from bot import Irene
from helpers import LOGGER, send_message, SmartButtons, new_task
from helpers.guard import admin_only
from database.store import DataStore


def _pfx(cmds):
    esc    = "".join(c if c.isalpha() else f"\\{c}" for c in config.COMMAND_PREFIXES)
    joined = "|".join(cmds)
    return rf"^[{esc}]({joined})(?:\s|$)"


async def _is_admin(user_id: int) -> bool:
    if user_id == config.ADMIN_ID:
        return True
    guards = await DataStore.get().get_guards()
    return user_id in [g["user_id"] for g in guards]


def _log_stats():
    if not os.path.exists("botlog.txt"):
        return None, None, None
    size_kb    = os.path.getsize("botlog.txt") / 1024
    with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
        line_count = sum(1 for _ in f)
    return size_kb, line_count, datetime.now()


def _log_caption(size_kb, line_count, now):
    return (
        "<b>Smart Logs Check → Successful ✅</b>\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>⊗ File Size:</b> {size_kb:.2f} KB\n"
        f"<b>⊗ Log Lines:</b> {line_count} Lines\n"
        f"<b>⊗ Time:</b> {now.strftime('%H:%M:%S')}\n"
        f"<b>⊗ Date:</b> {now.strftime('%Y-%m-%d')}\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        "<b>Smart LogsChecker → Activated ✅</b>"
    )


def _log_buttons():
    sb = SmartButtons()
    sb.button(text="📋 Display Logs", callback_data="logs_display")
    sb.button(text="❌ Close",         callback_data="logs_close",   position="footer")
    return sb.build_menu(b_cols=1, f_cols=1)


@Irene.on(events.NewMessage(pattern=_pfx(["logs"])))
@admin_only
async def logs_handler(event):
    chat_id = event.chat_id
    prog    = await send_message(chat_id, "<b>Checking The Logs...💥</b>", parse_mode="html")
    await asyncio.sleep(2)

    try:
        if not os.path.exists("botlog.txt"):
            await Irene.edit_message(chat_id, prog, "<b>Sorry, No Logs Found ❌</b>", parse_mode="html")
            await asyncio.sleep(2)
            await Irene.delete_messages(chat_id, [prog.id])
            return

        size_kb, line_count, now = _log_stats()
        caption = _log_caption(size_kb, line_count, now)
        buttons = _log_buttons()

        await Irene.delete_messages(chat_id, [prog.id])
        await Irene.send_file(
            chat_id,
            "botlog.txt",
            caption=caption,
            parse_mode="html",
            buttons=buttons,
            force_document=True,
        )
        LOGGER.info(f"Sent logs document to {chat_id}")

    except Exception as e:
        LOGGER.error(f"logs_handler error: {e}")
        try:
            await Irene.edit_message(chat_id, prog, "<b>❌ Failed to process logs command!</b>", parse_mode="html")
        except Exception:
            pass


@Irene.on(events.CallbackQuery(data=b"logs_close"))
async def logs_close_cb(event):
    if not await _is_admin(event.sender_id):
        return
    try:
        await event.delete()
    except Exception as e:
        LOGGER.error(f"logs_close_cb error: {e}")


@Irene.on(events.CallbackQuery(data=b"logs_display"))
async def logs_display_cb(event):
    if not await _is_admin(event.sender_id):
        return
    chat_id = event.chat_id
    try:
        await event.answer()
        if not os.path.exists("botlog.txt"):
            await send_message(chat_id, "<b>Sorry, No Logs Found ❌</b>", parse_mode="html")
            return

        with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        latest = lines[-20:] if len(lines) > 20 else lines
        text   = "".join(latest)
        if len(text) > 4096:
            text = text[-4096:]

        sb = SmartButtons()
        sb.button(text="🔙 Back", callback_data="logs_close")

        await send_message(
            chat_id,
            text if text.strip() else "No logs available. ❌",
            buttons=sb.build_menu(b_cols=1),
        )

    except Exception as e:
        LOGGER.error(f"logs_display_cb error: {e}")
        await event.answer("❌ Failed to display logs!", alert=True)
