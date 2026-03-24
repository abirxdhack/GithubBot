import math
import re

from telethon import events
from telethon.tl.types import User

import config
from bot import Irene
from crypto.vault import seal, unseal
from database.models import LinkedRepo
from database.store import DataStore
from ghub.events import SUPPORTED
from ghub.ghclient import GhApi, GhApiError
from ghub.oauth import build_auth_url
from helpers import LOGGER, send_message, SmartButtons, split_repo, new_task, clean_download
from modules.admins import is_admin

_prefixes = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)


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


async def push_repo_picker(chat_id: int, tg_id: int, page: int, edit_msg_id=None):
    api = await _get_api(tg_id)
    if not api:
        await send_message(chat_id, "Please /connect your GitHub account first.")
        return

    try:
        repos = await api.list_repos(page=page, per_page=5)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _revoke_warn(chat_id, tg_id)
            return
        await send_message(chat_id, "Failed to fetch repositories from GitHub.")
        return

    if not repos and page == 1:
        await send_message(chat_id, "No repositories found on your GitHub account.")
        return

    sb = SmartButtons()
    for r in repos:
        sb.button(r["full_name"], callback_data=f"c:ar:id:{r['id']}")

    has_next = len(repos) == 5
    if page > 1:
        sb.button("◀ Prev", callback_data=f"c:ar:pg:{page - 1}", position="footer")
    for i in range(max(1, page - 1), page + 2):
        if i == page or (i == page + 1 and has_next) or (i == page - 1 and page > 1):
            label = f"· {i} ·" if i == page else str(i)
            sb.button(label, callback_data=f"c:ar:pg:{i}", position="footer")
    if has_next:
        sb.button("Next ▶", callback_data=f"c:ar:pg:{page + 1}", position="footer")

    markup = sb.build_menu(b_cols=1, f_cols=6)
    text   = f"Select a repository to add (Page {page}):"

    if edit_msg_id:
        from helpers import edit_message
        await edit_message(chat_id, edit_msg_id, text, parse_mode="html", buttons=markup)
    else:
        await send_message(chat_id, text, parse_mode="html", buttons=markup)


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]addrepo(?:\s|$)", re.IGNORECASE)))
@new_task
async def addrepo_handler(event):
    chat  = await event.get_chat()
    is_dm = isinstance(chat, User)
    if not is_dm and not await is_admin(event.chat_id, event.sender_id):
        await send_message(event.chat_id, "Only admins can add repositories.")
        return

    raw = event.message.text.split(None, 2)
    if len(raw) < 2:
        await push_repo_picker(event.chat_id, event.sender_id, page=1)
        return

    full_name = raw[1].strip()
    owner, repo = split_repo(full_name)
    if not owner or not repo:
        await send_message(event.chat_id, "Invalid format. Use: /addrepo owner/repo")
        return

    api = await _get_api(event.sender_id)
    if not api:
        url = build_auth_url("connect")
        await send_message(event.chat_id, f'Please <a href="{url}">connect your GitHub account</a> first.', parse_mode="html")
        return

    try:
        await api.get_repo(full_name)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _revoke_warn(event.chat_id, event.sender_id)
            return
        if exc.status == 404:
            await send_message(event.chat_id, "❌ <b>Repository not found.</b>\nCheck the name and ensure you have access.", parse_mode="html")
            return
        await send_message(event.chat_id, f"Error fetching repository: {exc.message}")
        return

    chat_token   = seal(str(event.chat_id))
    webhook_url  = f"{config.PUBLIC_URL}/webhook/{chat_token}"
    default_evts = [e.key for e in SUPPORTED]

    try:
        hook = await api.create_hook(owner, repo, webhook_url, config.HOOK_SECRET, default_evts)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _revoke_warn(event.chat_id, event.sender_id)
            return
        if exc.status == 404:
            await send_message(event.chat_id, f"❌ <b>Insufficient permissions.</b>\nYou need admin access to <b>{full_name}</b> to create webhooks.", parse_mode="html")
            return
        LOGGER.error(f"Webhook creation failed for {full_name}: {exc}")
        await send_message(event.chat_id, "⚠️ <b>Webhook creation failed.</b>\nEnsure you have admin rights and try again.", parse_mode="html")
        return

    await DataStore.get().add_repo(event.chat_id, LinkedRepo(name=full_name, hook_id=hook["id"]))
    await send_message(event.chat_id, f"✅ Repository <b>{full_name}</b> linked successfully!", parse_mode="html")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]removerepo(?:\s|$)", re.IGNORECASE)))
@new_task
async def removerepo_handler(event):
    chat  = await event.get_chat()
    is_dm = isinstance(chat, User)
    if not is_dm and not await is_admin(event.chat_id, event.sender_id):
        await send_message(event.chat_id, "Only admins can remove repositories.")
        return

    raw = event.message.text.split(None, 2)
    if len(raw) < 2:
        await send_message(event.chat_id, "Usage: /removerepo owner/repo")
        return

    full_name = raw[1].strip()
    store     = DataStore.get()
    link      = await store.get_repo(event.chat_id, full_name)
    if not link:
        await send_message(event.chat_id, "Repository link not found.")
        return

    hook_note = ""
    if link.hook_id:
        api = await _get_api(event.sender_id)
        if not api:
            hook_note = "\n\n⚠️ <b>Warning:</b> Not connected to GitHub. Remove the webhook manually."
        else:
            owner, repo = split_repo(full_name)
            if owner and repo:
                try:
                    await api.delete_hook(owner, repo, link.hook_id)
                except GhApiError as exc:
                    if exc.status in (401, 403):
                        hook_note = "\n\n⚠️ <b>Warning:</b> GitHub auth failed. Webhook not removed."
                    elif exc.status != 404:
                        hook_note = f"\n\n⚠️ <b>Warning:</b> Failed to delete webhook: {exc.message}"

    await store.remove_repo(event.chat_id, full_name)
    await send_message(event.chat_id, f"✅ Repository <b>{full_name}</b> removed.{hook_note}", parse_mode="html")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]repos(?:\s|$)", re.IGNORECASE)))
@new_task
async def repos_handler(event):
    store = DataStore.get()
    links = await store.list_repos(event.chat_id)
    if not links:
        await send_message(event.chat_id, "No repositories linked. Use /addrepo to link one.")
        return
    lines = "".join(f"• <b>{l.name}</b>\n" for l in links)
    await send_message(event.chat_id, f"<b>📦 Linked Repositories:</b>\n\n{lines}", parse_mode="html")


@Irene.on(events.NewMessage(pattern=re.compile(rf"^[{_prefixes}]settings(?:\s|$)", re.IGNORECASE)))
@new_task
async def settings_handler(event):
    chat  = await event.get_chat()
    is_dm = isinstance(chat, User)
    if not is_dm and not await is_admin(event.chat_id, event.sender_id):
        await send_message(event.chat_id, "Only admins can modify settings.")
        return

    store = DataStore.get()
    links = await store.list_repos(event.chat_id)
    if not links:
        await send_message(event.chat_id, "No repositories linked. Use /addrepo first.")
        return

    prog = await send_message(event.chat_id, "⏳ <b>Validating linked repositories...</b>", parse_mode="html")

    api       = await _get_api(event.sender_id)
    valid     = []
    removed   = []

    for l in links:
        if api:
            try:
                await api.get_repo(l.name)
                valid.append(l)
            except GhApiError as exc:
                if exc.status == 404:
                    await store.remove_repo(event.chat_id, l.name)
                    removed.append(l.name)
                    LOGGER.info(f"Auto-removed stale repo {l.name} from chat {event.chat_id}")
                else:
                    valid.append(l)
            except Exception:
                valid.append(l)
        else:
            valid.append(l)

    try:
        await Irene.delete_messages(event.chat_id, [prog.id])
    except Exception:
        pass

    if removed:
        note = "\n".join(f"• <code>{r}</code>" for r in removed)
        await send_message(
            event.chat_id,
            f"🗑️ <b>Auto-removed {len(removed)} deleted repo(s):</b>\n{note}",
            parse_mode="html",
        )

    if not valid:
        await send_message(event.chat_id, "No valid repositories linked. Use /addrepo to link one.")
        return

    sb = SmartButtons()
    for l in valid:
        sb.button(l.name, callback_data=f"c:r:{l.name}")
    await send_message(event.chat_id, "Select a repository to configure:", buttons=sb.build_menu(b_cols=1))