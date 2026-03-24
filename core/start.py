import asyncio
import re

from telethon import events

import config
from bot import Irene
from ghub.genbtn import build_start_buttons
from helpers import LOGGER, send_message, edit_message, new_task
from helpers.guard import ban_check


_prefixes = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_pat      = re.compile(rf"^[{_prefixes}](start|help)(?:\s|$)", re.IGNORECASE)


def get_start_text(name: str) -> str:
    return (
        f"**Hi {name}! Welcome To GitHub Notify Bot**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "**GitHub Notify Bot ⚙️** is your ultimate GitHub integration for Telegram — "
        "receive instant notifications for push events, PRs, issues, reviews, deployments and more!\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Don't forget to [join](https://{config.UPDATES_URL}) for updates!"
    )


@Irene.on(events.NewMessage(pattern=_pat))
@ban_check
@new_task
async def start_handler(event):
    sender     = await event.get_sender()
    first_name = getattr(sender, "first_name", "") or ""
    last_name  = getattr(sender, "last_name", "") or ""
    name       = f"{first_name} {last_name}".strip() or "there"

    LOGGER.info(f"/start — user: {name} ({sender.id})")

    msg = await send_message(event.chat_id, "**Starting GitHub Notify Bot ⚙️....**", parse_mode="md")
    if not msg:
        return

    await asyncio.sleep(0.3)
    await edit_message(event.chat_id, msg.id, "**Generating Session Keys...**", parse_mode="md")
    await asyncio.sleep(0.3)

    await edit_message(
        event.chat_id, msg.id,
        get_start_text(name),
        parse_mode="md",
        link_preview=False,
        buttons=build_start_buttons(),
    )
