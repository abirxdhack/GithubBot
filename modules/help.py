import re

from telethon import events

import config
from bot import Irene
from helpers import send_message, SmartButtons, new_task

_prefixes  = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_help_pat  = re.compile(rf"^[{_prefixes}]help(?:\s|$)",    re.IGNORECASE)
_priv_pat  = re.compile(rf"^[{_prefixes}]privacy(?:\s|$)", re.IGNORECASE)


def _back_markup():
    sb = SmartButtons()
    sb.button("⬅️ Back to Start", callback_data="back_to_start")
    return sb.build_menu(b_cols=1)


@Irene.on(events.NewMessage(pattern=_help_pat))
@new_task
async def help_handler(event):
    text = (
        "<b>📖 GitHub Notify Bot — Commands</b>\n\n"
        "<b>Account</b>\n"
        "• /connect — Link your GitHub account <i>(private chat only)</i>\n"
        "• /logout  — Unlink your GitHub account\n\n"
        "<b>Repository Management</b>\n"
        "• /addrepo [owner/repo] — Link a repository\n"
        "• /removerepo [owner/repo] — Unlink a repository\n"
        "• /repos — List all linked repositories\n\n"
        "<b>Actions</b> <i>(reply to a notification)</i>\n"
        "• /close   — Close an issue or PR\n"
        "• /reopen  — Reopen an issue or PR\n"
        "• /approve — Approve a pull request\n\n"
        "<b>Configuration</b>\n"
        "• /settings — Configure per-repo event notifications\n"
        "• /reload   — Reload admin permission cache\n\n"
        "<b>Info</b>\n"
        "• /help    — Show this message\n"
        "• /privacy — Privacy policy"
    )
    await send_message(event.chat_id, text, parse_mode="html",
                       link_preview=False, buttons=_back_markup())


@Irene.on(events.NewMessage(pattern=_priv_pat))
@new_task
async def privacy_handler(event):
    text = (
        "<b>🔐 Privacy Policy</b>\n\n"
        "<b>1. Data We Collect</b>\n"
        "• Telegram User ID and Chat ID — routing notifications and access control.\n"
        "• Encrypted GitHub OAuth token — stored in MongoDB, never in plain text.\n"
        "• Repository names and webhook IDs — to manage linked repos.\n"
        "• Webhook payloads — processed in real-time, never stored permanently.\n\n"
        "<b>2. How We Use It</b>\n"
        "• Strictly to deliver GitHub notifications and handle bot commands.\n"
        "• Tokens encrypted with AES-256-GCM before storage.\n\n"
        "<b>3. Data Sharing</b>\n"
        "• We do <b>not</b> share, sell, or rent your data to any third party.\n\n"
        "<b>4. Your Rights</b>\n"
        "• /logout to revoke your stored GitHub token.\n"
        "• /removerepo to delete linked repository records.\n\n"
        "<b>5. Contact</b>\n"
        "Open an issue on the project repository."
    )
    await send_message(event.chat_id, text, parse_mode="html",
                       link_preview=False, buttons=_back_markup())