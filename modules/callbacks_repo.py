import math

from telethon import events

from telethon.tl.types import User, Channel, Chat

import config
from bot import Irene
from database.models import LinkedRepo
from database.store import DataStore
from ghub.events import SUPPORTED, SHORT_TO_KEY
from ghub.ghclient import GhApi, GhApiError
from helpers import LOGGER, SmartButtons, split_repo
from crypto.vault import seal, unseal

_peer_session: dict = {}


async def _get_api(tg_id: int):
    account = await DataStore.get().get_account(tg_id)
    if not account or not account.token_enc:
        return None
    try:
        return GhApi(unseal(account.token_enc))
    except Exception:
        return None


async def _auth_fail_cb(event, tg_id: int):
    await DataStore.get().clear_token(tg_id)
    await event.answer("GitHub auth error — token revoked or expired.", alert=True)


async def route_repo_callback(event, data: str):
    if data.startswith("pr:"):
        await _pr_action(event, data)
        return

    parts = data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]

    if action == "ls":
        await _show_repo_list(event)
        return

    if action == "ar":
        if len(parts) < 4:
            return
        sub, val = parts[2], parts[3]
        if sub == "pg":
            await _repo_picker_page(event, int(val))
        elif sub == "id":
            await _add_repo_by_id(event, int(val))
        return

    if len(parts) < 3:
        return

    repo_name = parts[2]
    link      = await DataStore.get().get_repo(event.chat_id, repo_name)

    if action == "r":
        if not link:
            await event.answer("Repo not found.", alert=False)
            return
        await _show_repo_menu(event, link)
        return

    if action == "dest" and len(parts) == 3:
        await _ask_dest_type(event, repo_name)
        return

    if action == "dtype" and len(parts) == 4:
        await _ask_peer_id(event, repo_name, parts[3])
        return

    if action == "dcancel" and len(parts) == 3:
        _peer_session.pop(event.sender_id, None)
        await event.edit("<b>Choosing ChatType Cancelled ❌</b>", parse_mode="html")
        return

    if action == "presets" and len(parts) == 4:
        if not link:
            await event.answer("Repo not found.", alert=False)
            return
        await _apply_preset(event, link, parts[3])
        return

    if action in ("iev", "ep") and len(parts) == 4:
        if not link:
            await event.answer("Repo not found.", alert=False)
            return
        await _show_event_toggles(event, link, int(parts[3]))
        return

    if action == "te" and len(parts) >= 4:
        if not link:
            await event.answer("Repo not found.", alert=False)
            return
        abbr = parts[3]
        page = int(parts[4]) if len(parts) == 5 else 1
        await _toggle_event(event, link, abbr, page)
        return


async def _show_repo_list(event):
    links = await DataStore.get().list_repos(event.chat_id)
    if not links:
        await event.edit("No repositories linked. Use /addrepo first.")
        return
    sb = SmartButtons()
    for l in links:
        sb.button(l.name, callback_data=f"c:r:{l.name}")
    await event.edit("Select a repository to configure:", buttons=sb.build_menu(b_cols=1))


async def _show_repo_menu(event, link: LinkedRepo):
    sb = SmartButtons()
    sb.button("📌 Push events only",        callback_data=f"c:presets:{link.name}:push")
    sb.button("📡 Send me everything",       callback_data=f"c:presets:{link.name}:all")
    sb.button("🎛 Choose individual events", callback_data=f"c:iev:{link.name}:1")
    dest_label = "📍 Update Destination ✅" if link.peer_id else "📍 Set Update Destination"
    sb.button(dest_label,                    callback_data=f"c:dest:{link.name}")
    sb.button("⬅️ Back to repo list",        callback_data="c:ls", position="footer")
    await event.edit(
        f"⚙️ <b>Configuration for {link.name}:</b>",
        parse_mode="html",
        buttons=sb.build_menu(b_cols=1, f_cols=1),
    )


async def _apply_preset(event, link: LinkedRepo, mode: str):
    api = await _get_api(event.sender_id)
    if not api:
        await event.answer("Please /connect to GitHub first.", alert=True)
        return

    owner, repo_name = split_repo(link.name)
    if not owner or not repo_name:
        return

    try:
        hook = await api.get_hook(owner, repo_name, link.hook_id)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("Failed to fetch GitHub hook.", alert=True)
        return

    new_events = ["push"] if mode == "push" else ["*"]
    response   = "✅ <b>Updated — push events only.</b>" if mode == "push" else "✅ <b>Updated — sending everything.</b>"
    hook_url   = hook.get("config", {}).get("url", "")

    try:
        await api.edit_hook(owner, repo_name, link.hook_id, new_events, hook_url, config.HOOK_SECRET)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("Failed to update hook.", alert=True)
        return

    sb = SmartButtons()
    sb.button("⬅️ Back", callback_data=f"c:r:{link.name}")
    await event.edit(response, parse_mode="html", buttons=sb.build_menu(b_cols=1))


async def _show_event_toggles(event, link: LinkedRepo, page: int):
    api = await _get_api(event.sender_id)
    if not api:
        await event.edit("Error: connect your GitHub account first via /connect")
        return

    owner, repo_name = split_repo(link.name)
    if not owner or not repo_name:
        return

    try:
        hook = await api.get_hook(owner, repo_name, link.hook_id)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await DataStore.get().clear_token(event.sender_id)
        await event.edit("Error fetching webhook settings. Check permissions.")
        return

    active = set()
    for e in (hook.get("events") or []):
        if e == "*":
            active = {ev.key for ev in SUPPORTED}
            break
        active.add(e)

    sb = SmartButtons()
    for ev in SUPPORTED:
        tick = "✅" if ev.key in active else "❌"
        sb.button(f"{tick} {ev.label}", callback_data=f"c:te:{link.name}:{ev.short}:{page}")

    gh_url = f"https://github.com/{owner}/{repo_name}/settings/hooks/{link.hook_id}"
    sb.button("🌐 Edit more on GitHub", url=gh_url,                       position="footer")
    sb.button("⬅️ Back",                callback_data=f"c:r:{link.name}", position="footer")

    await event.edit(
        f"🎛 <b>Individual events for {link.name}:</b>",
        parse_mode="html",
        buttons=sb.build_menu(b_cols=2, f_cols=2),
    )


async def _toggle_event(event, link: LinkedRepo, abbr: str, page: int):
    api = await _get_api(event.sender_id)
    if not api:
        await event.answer("Please /connect to GitHub first.", alert=True)
        return

    evt_key          = SHORT_TO_KEY.get(abbr, abbr)
    owner, repo_name = split_repo(link.name)
    if not owner or not repo_name:
        return

    try:
        hook = await api.get_hook(owner, repo_name, link.hook_id)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("Failed to fetch settings.", alert=True)
        return

    current  = []
    wildcard = False
    for e in (hook.get("events") or []):
        if e == "*":
            wildcard = True
            break
        current.append(e)

    if wildcard:
        current = [ev.key for ev in SUPPORTED]

    new_events = [e for e in current if e != evt_key] if evt_key in current else current + [evt_key]
    hook_url   = hook.get("config", {}).get("url", "")

    try:
        await api.edit_hook(owner, repo_name, link.hook_id, new_events, hook_url, config.HOOK_SECRET)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("Failed to update GitHub.", alert=True)
        return

    await _show_event_toggles(event, link, page)


async def _repo_picker_page(event, page: int):
    api = await _get_api(event.sender_id)
    if not api:
        await event.answer("Auth error. Please /connect again.", alert=True)
        return

    try:
        repos = await api.list_repos(page=page, per_page=5)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("GitHub API error.", alert=True)
        return

    if not repos:
        await event.answer("No more repositories.", alert=False)
        return

    has_next = len(repos) == 5
    sb = SmartButtons()
    for r in repos:
        sb.button(r["full_name"], callback_data=f"c:ar:id:{r['id']}")

    if page > 1:
        sb.button("⬅️ Prev", callback_data=f"c:ar:pg:{page - 1}", position="footer")
    for i in range(max(1, page - 1), page + 2):
        if i == page or (i == page + 1 and has_next) or (i == page - 1 and page > 1):
            label = f"· {i} ·" if i == page else str(i)
            sb.button(label, callback_data=f"c:ar:pg:{i}", position="footer")
    if has_next:
        sb.button("Next ➡️", callback_data=f"c:ar:pg:{page + 1}", position="footer")

    await event.edit(
        f"Select a repository to add (Page {page}):",
        buttons=sb.build_menu(b_cols=1, f_cols=6),
    )


async def _add_repo_by_id(event, repo_id: int):
    api = await _get_api(event.sender_id)
    if not api:
        await event.answer("Auth error. Please /connect again.", alert=True)
        return

    try:
        gh_repo = await api.get_repo_by_id(repo_id)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer("Repo not found or access denied.", alert=True)
        return

    full_name    = gh_repo["full_name"]
    owner        = gh_repo["owner"]["login"]
    repo_name    = gh_repo["name"]
    chat_token   = seal(str(event.chat_id))
    webhook_url  = f"{config.PUBLIC_URL}/webhook/{chat_token}"
    default_evts = [e.key for e in SUPPORTED]

    try:
        hook = await api.create_hook(owner, repo_name, webhook_url, config.HOOK_SECRET, default_evts)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.edit(f"⚠️ Webhook creation failed: {exc.message}\nCheck that you have admin access.", parse_mode="html")
        return

    await DataStore.get().add_repo(event.chat_id, LinkedRepo(name=full_name, hook_id=hook["id"]))
    await event.edit(f"✅ Repository <b>{full_name}</b> linked successfully!", parse_mode="html")


async def _pr_action(event, data: str):
    parts = data.split(":")
    if len(parts) != 4:
        return

    action, repo_full, pr_num = parts[1], parts[2], int(parts[3])
    link = await DataStore.get().get_repo(event.chat_id, repo_full)
    if not link:
        await event.answer("This chat is not linked to that repo.", alert=True)
        return

    api = await _get_api(event.sender_id)
    if not api:
        await event.answer("Please /connect your GitHub account first.", alert=True)
        return

    owner, repo_name = split_repo(repo_full)
    if not owner or not repo_name:
        return

    try:
        if action == "approve":
            await api.approve_pr(owner, repo_name, pr_num)
            label = "Approved!"
        elif action == "close":
            await api.close_pr(owner, repo_name, pr_num)
            label = "Closed!"
        else:
            return
    except GhApiError as exc:
        if exc.status in (401, 403):
            await _auth_fail_cb(event, event.sender_id)
            return
        await event.answer(f"Failed: {exc.message}", alert=True)
        return

    await event.answer(label, alert=True)


async def _ask_dest_type(event, repo_name: str):
    sb = SmartButtons()
    sb.button("📥 Inbox",    callback_data=f"c:dtype:{repo_name}:user")
    sb.button("📢 Channel",  callback_data=f"c:dtype:{repo_name}:channel")
    sb.button("💬 Group",    callback_data=f"c:dtype:{repo_name}:group")
    sb.button("❌ Cancel",   callback_data=f"c:dcancel:{repo_name}", position="footer")
    await event.edit(
        "<b>Where You Want To Get The Updates?</b>\n"
        "<b>Choose from below buttons:</b>",
        parse_mode="html",
        buttons=sb.build_menu(b_cols=2, f_cols=1),
    )


async def _ask_peer_id(event, repo_name: str, dest_type: str):
    _peer_session[event.sender_id] = {
        "repo_name": repo_name,
        "chat_id":   event.chat_id,
        "dest_type": dest_type,
        "msg_id":    event.message_id,
    }
    type_hints = {
        "user":    "User ID e.g. <code>7666341631</code>",
        "channel": "Channel ID e.g. <code>-1001234567890</code>",
        "group":   "Group ID e.g. <code>-1009876543210</code>",
    }
    sb = SmartButtons()
    sb.button("❌ Cancel", callback_data=f"c:dcancel:{repo_name}")
    await event.edit(
        "<b>Send The Chat-ID Where To Receive Updates</b>\n"
        "<b>Must Do Before Doing</b>\n"
        "1. Make Sure I Know The Peer.\n"
        "2. I Am Added There As An Admin.\n"
        "3. Must Provide Me Full Permission\n\n"
        f"<b>Expected:</b> {type_hints.get(dest_type, 'Chat ID')}\n\n"
        "<b>Click below button for cancel</b>",
        parse_mode="html",
        buttons=sb.build_menu(b_cols=1),
    )




@Irene.on(events.NewMessage(incoming=True))
async def _peer_input_listener(event):
    try:
        if not event.message or not event.sender_id:
            return
        if event.sender_id not in _peer_session:
            return
        from helpers.guard import ban_check as _ban_check
        await handle_peer_input(event)
    except Exception as e:
        LOGGER.error(f"_peer_input_listener error: {e}")

async def handle_peer_input(event) -> bool:
    sender_id = event.sender_id
    if sender_id not in _peer_session:
        return False
    session = _peer_session.get(sender_id)
    if not session or session.get("chat_id") != event.chat_id:
        return False

    raw = (event.message.text or "").strip()
    if not raw:
        return True

    repo_name = session["repo_name"]
    dest_type = session["dest_type"]

    try:
        peer_id = int(raw)
    except ValueError:
        try:
            ent     = await Irene.get_entity(raw)
            peer_id = ent.id
            if isinstance(ent, Channel):
                peer_id = int(f"-100{abs(ent.id)}")
        except Exception:
            await event.respond("<b>Sorry Peer Id Invalid ❌</b>", parse_mode="html")
            return True

    checking = await event.respond("<b>Checking Peer ID For Validation...</b>", parse_mode="html")

    try:
        ent = await Irene.get_entity(peer_id)
    except Exception as e:
        LOGGER.warning(f"Peer validation failed {peer_id}: {e}")
        await Irene.edit_message(event.chat_id, checking.id, "<b>Sorry Peer Id Invalid ❌</b>", parse_mode="html")
        return True

    is_channel = isinstance(ent, Channel) and getattr(ent, "broadcast", False)
    is_group   = isinstance(ent, Chat) or (isinstance(ent, Channel) and getattr(ent, "megagroup", False))
    is_user    = isinstance(ent, User)

    valid = (
        (dest_type == "channel" and is_channel) or
        (dest_type == "group"   and is_group)   or
        (dest_type == "user"    and (is_user or peer_id > 0))
    )

    if not valid:
        expected = {"channel": "a Channel", "group": "a Group", "user": "a User"}.get(dest_type, "correct type")
        await Irene.edit_message(
            event.chat_id, checking.id,
            f"<b>Sorry Peer Id Invalid ❌</b>\nExpected {expected}.",
            parse_mode="html",
        )
        return True

    await DataStore.get().set_repo_peer(event.chat_id, repo_name, peer_id)
    _peer_session.pop(sender_id, None)

    ent_name = getattr(ent, "title", None) or getattr(ent, "first_name", None) or str(peer_id)
    await Irene.edit_message(
        event.chat_id, checking.id,
        f"<b>Peer Successfully Connected ✅</b>\n\n"
        f"Updates for <b>{repo_name}</b> will now be sent to\n"
        f"<b>{ent_name}</b> (<code>{peer_id}</code>)",
        parse_mode="html",
    )
    return True