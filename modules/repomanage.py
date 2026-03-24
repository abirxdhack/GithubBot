import re

from telethon import events
from telethon.errors import MessageNotModifiedError
from telethon.tl.types import User

import config
from bot import Irene
from cache.ttlcache import TTLCache
from crypto.vault import unseal
from database.store import DataStore
from ghub.ghclient import GhApi, GhApiError
from helpers import LOGGER, send_message, edit_message, SmartButtons, new_task, split_repo
from helpers.guard import ban_check

_prefixes      = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_del_pat       = re.compile(rf"^[{_prefixes}]del(?:\s|$)",            re.IGNORECASE)
_setdesc_pat   = re.compile(rf"^[{_prefixes}]setdescription(?:\s|$)", re.IGNORECASE)
_sethandle_pat = re.compile(rf"^[{_prefixes}]sethandle(?:\s|$)",      re.IGNORECASE)

_desc_sessions:   TTLCache = TTLCache()
_handle_sessions: TTLCache = TTLCache()

_PER_PAGE = 8


async def _get_api(tg_id: int):
    acc = await DataStore.get().get_account(tg_id)
    if not acc or not acc.token_enc:
        return None
    try:
        return GhApi(unseal(acc.token_enc))
    except Exception:
        return None


async def _check_connected(chat_id: int, sender_id: int) -> bool:
    api = await _get_api(sender_id)
    if not api:
        await send_message(
            chat_id,
            "**❌Please connect your github acc first**",
            parse_mode="md",
        )
        return False
    return True


async def _send_repo_picker(chat_id: int, sender_id: int, cb_prefix: str, page: int = 1) -> None:
    api = await _get_api(sender_id)
    if not api:
        await send_message(chat_id, "**❌Please connect your github acc first**", parse_mode="md")
        return

    try:
        repos = await api.list_repos(page=page, per_page=_PER_PAGE)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await DataStore.get().clear_token(sender_id)
            await send_message(chat_id, "**❌ GitHub auth failed. Please /connect again.**", parse_mode="md")
        else:
            await send_message(chat_id, "**❌ Failed to fetch repositories from GitHub.**", parse_mode="md")
        return
    except Exception as exc:
        LOGGER.error(f"_send_repo_picker list_repos error: {exc}")
        await send_message(chat_id, "**❌ Failed to fetch repositories from GitHub.**", parse_mode="md")
        return

    if not repos and page == 1:
        await send_message(chat_id, "**No repositories found on your GitHub account.**", parse_mode="md")
        return

    if not repos:
        await send_message(chat_id, "**No more repositories.**", parse_mode="md")
        return

    has_next = len(repos) == _PER_PAGE

    sb = SmartButtons()
    for r in repos:
        sb.button(r["full_name"], callback_data=f"{cb_prefix}:{r['full_name']}")

    if page > 1:
        sb.button("◀ Prev", callback_data=f"{cb_prefix}_pg:{page - 1}", position="footer")
    if has_next:
        sb.button("Next ▶", callback_data=f"{cb_prefix}_pg:{page + 1}", position="footer")

    await send_message(
        chat_id,
        f"**Select a repository (Page {page}):**",
        parse_mode="md",
        buttons=sb.build_menu(b_cols=1, f_cols=2),
    )


async def _edit_repo_picker(event, sender_id: int, cb_prefix: str, page: int) -> None:
    api = await _get_api(sender_id)
    if not api:
        await event.edit("**❌Please connect your github acc first**", parse_mode="md")
        return

    try:
        repos = await api.list_repos(page=page, per_page=_PER_PAGE)
    except GhApiError as exc:
        if exc.status in (401, 403):
            await DataStore.get().clear_token(sender_id)
            await event.edit("**❌ GitHub auth failed. Please /connect again.**", parse_mode="md")
        else:
            await event.edit("**❌ Failed to fetch repositories from GitHub.**", parse_mode="md")
        return
    except Exception as exc:
        LOGGER.error(f"_edit_repo_picker list_repos error: {exc}")
        await event.edit("**❌ Failed to fetch repositories from GitHub.**", parse_mode="md")
        return

    if not repos:
        await event.edit("**No more repositories.**", parse_mode="md")
        return

    has_next = len(repos) == _PER_PAGE

    sb = SmartButtons()
    for r in repos:
        sb.button(r["full_name"], callback_data=f"{cb_prefix}:{r['full_name']}")

    if page > 1:
        sb.button("◀ Prev", callback_data=f"{cb_prefix}_pg:{page - 1}", position="footer")
    if has_next:
        sb.button("Next ▶", callback_data=f"{cb_prefix}_pg:{page + 1}", position="footer")

    await event.edit(
        f"**Select a repository (Page {page}):**",
        parse_mode="md",
        buttons=sb.build_menu(b_cols=1, f_cols=2),
    )


def _proceed_cancel_row(proceed_data: str, cancel_data: str):
    sb = SmartButtons()
    sb.button("✅ Proceed", callback_data=proceed_data)
    sb.button("❌ Cancel",  callback_data=cancel_data)
    return sb.build_menu(b_cols=2)


@Irene.on(events.NewMessage(pattern=_del_pat))
@new_task
async def del_cmd(e):
    if not await _check_connected(e.chat_id, e.sender_id):
        return
    await _send_repo_picker(e.chat_id, e.sender_id, "rm:pick", page=1)


@Irene.on(events.NewMessage(pattern=_setdesc_pat))
@new_task
async def setdesc_cmd(e):
    if not await _check_connected(e.chat_id, e.sender_id):
        return
    await _send_repo_picker(e.chat_id, e.sender_id, "sd:pick", page=1)


@Irene.on(events.NewMessage(pattern=_sethandle_pat))
@new_task
async def sethandle_cmd(e):
    if not await _check_connected(e.chat_id, e.sender_id):
        return
    await _send_repo_picker(e.chat_id, e.sender_id, "sh:pick", page=1)


@Irene.on(events.CallbackQuery(pattern=rb"^rm:pick_pg:"))
@ban_check
async def rm_pg_cb(e):
    page = int(e.data.decode().split("rm:pick_pg:", 1)[1])
    await _edit_repo_picker(e, e.sender_id, "rm:pick", page)
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^sd:pick_pg:"))
@ban_check
async def sd_pg_cb(e):
    page = int(e.data.decode().split("sd:pick_pg:", 1)[1])
    await _edit_repo_picker(e, e.sender_id, "sd:pick", page)
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^sh:pick_pg:"))
@ban_check
async def sh_pg_cb(e):
    page = int(e.data.decode().split("sh:pick_pg:", 1)[1])
    await _edit_repo_picker(e, e.sender_id, "sh:pick", page)
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^rm:pick:"))
@ban_check
async def rm_pick_cb(e):
    repo_name = e.data.decode().split("rm:pick:", 1)[1]
    try:
        await e.edit(
            f"**Do You Want To Delete This Repo?**\n`{repo_name}`",
            parse_mode="md",
            buttons=_proceed_cancel_row(
                proceed_data=f"rm:go:{repo_name}",
                cancel_data="rm:cancel",
            ),
        )
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^rm:go:"))
@ban_check
async def rm_go_cb(e):
    repo_name = e.data.decode().split("rm:go:", 1)[1]

    try:
        await e.edit("**Deleting Repository....**", parse_mode="md")
    except MessageNotModifiedError:
        pass

    api = await _get_api(e.sender_id)
    if not api:
        try:
            await e.edit("**Sorry Failed To Delete Repo**", parse_mode="md")
        except MessageNotModifiedError:
            pass
        await e.answer()
        return

    owner, repo = split_repo(repo_name)
    if not owner or not repo:
        try:
            await e.edit("**Sorry Failed To Delete Repo**", parse_mode="md")
        except MessageNotModifiedError:
            pass
        await e.answer()
        return

    has_scope = await api.has_scope("delete_repo")
    if not has_scope:
        from ghub.oauth import build_auth_url
        from crypto.vault import random_token
        from database.store import DataStore as _DS
        state = random_token()
        try:
            from modules.connect import get_state_cache
            await get_state_cache().put(state, e.sender_id, ttl=600)
        except Exception:
            pass
        url = build_auth_url(state)
        sb  = SmartButtons()
        sb.button("🔑 Re-Authorize GitHub", url=url)
        try:
            await e.edit(
                "**❌ Your token is missing the `delete_repo` scope.**\n\n"
                "Click below to re-authorize — no need to /logout, just click and approve.",
                parse_mode="md",
                buttons=sb.build_menu(b_cols=1),
            )
        except MessageNotModifiedError:
            pass
        await e.answer()
        return

    try:
        await api.delete_repo(owner, repo)
    except GhApiError as ex:
        LOGGER.error(f"delete_repo GhApiError {repo_name}: {ex}")
        if ex.status == 404:
            msg = "**❌ Repository Not Found**\nIt may have already been deleted on GitHub."
        elif ex.status == 403:
            msg = "**❌ Permission Denied**\nYou don't have admin access to delete this repository."
        else:
            msg = f"**❌ Sorry Failed To Delete Repo**\n`{ex.message}`"
        try:
            await e.edit(msg, parse_mode="md")
        except MessageNotModifiedError:
            pass
        await e.answer()
        return
    except Exception as ex:
        LOGGER.error(f"delete_repo error {repo_name}: {ex}")
        try:
            await e.edit("**❌ Sorry Failed To Delete Repo**", parse_mode="md")
        except MessageNotModifiedError:
            pass
        await e.answer()
        return

    try:
        await DataStore.get().remove_repo(e.chat_id, repo_name)
    except Exception as ex:
        LOGGER.warning(f"remove_repo from DB failed for {repo_name}: {ex}")

    try:
        await e.edit("** Successfully Deleted Repository**", parse_mode="md")
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.CallbackQuery(data=b"rm:cancel"))
@ban_check
async def rm_cancel_cb(e):
    try:
        await e.edit("**Cancelled ❌ Repo Deletation**", parse_mode="md")
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^sd:pick:"))
@ban_check
async def sd_pick_cb(e):
    repo_name = e.data.decode().split("sd:pick:", 1)[1]
    try:
        await e.edit(
            f"**Do You Want To Change Description Of This Repo?**\n`{repo_name}`",
            parse_mode="md",
            buttons=_proceed_cancel_row(
                proceed_data=f"sd:go:{repo_name}",
                cancel_data="sd:cancel",
            ),
        )
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^sd:go:"))
@ban_check
async def sd_go_cb(e):
    repo_name = e.data.decode().split("sd:go:", 1)[1]

    sb = SmartButtons()
    sb.button("❌ Cancel", callback_data="sd:cancel")

    try:
        await e.edit(
            "**Send The New Description Of The Repo**\n**Click Below Button To Cancel**",
            parse_mode="md",
            buttons=sb.build_menu(b_cols=1),
        )
    except MessageNotModifiedError:
        pass

    await _desc_sessions.put(e.sender_id, {
        "repo":   repo_name,
        "chat":   e.chat_id,
        "msg_id": e.message_id,
    }, ttl=300)

    await e.answer()


@Irene.on(events.CallbackQuery(data=b"sd:cancel"))
@ban_check
async def sd_cancel_cb(e):
    await _desc_sessions.delete(e.sender_id)
    try:
        await e.edit("**Cancelled ❌ Repo Deletation**", parse_mode="md")
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.NewMessage())
@new_task
async def desc_input_router(e):
    if not e.is_private:
        return
    if not e.text:
        return

    s = await _desc_sessions.get(e.sender_id)
    if not s:
        return

    new_desc  = e.text.strip()
    repo_name = s["repo"]
    msg_id    = s["msg_id"]
    chat_id   = s["chat"]

    if chat_id != e.chat_id:
        return

    await _desc_sessions.delete(e.sender_id)

    await edit_message(chat_id, msg_id, "**Changing Repo Description...**", parse_mode="md")

    api = await _get_api(e.sender_id)
    if not api:
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Description**", parse_mode="md")
        return

    owner, repo = split_repo(repo_name)
    if not owner or not repo:
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Description**", parse_mode="md")
        return

    try:
        await api.update_repo(owner, repo, description=new_desc)
        await edit_message(chat_id, msg_id, "**Successfully Changed Description**", parse_mode="md")
    except GhApiError as ex:
        LOGGER.error(f"update_repo description GhApiError {repo_name}: {ex}")
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Description**", parse_mode="md")
    except Exception as ex:
        LOGGER.error(f"update_repo description error {repo_name}: {ex}")
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Description**", parse_mode="md")


@Irene.on(events.CallbackQuery(pattern=rb"^sh:pick:"))
@ban_check
async def sh_pick_cb(e):
    repo_name = e.data.decode().split("sh:pick:", 1)[1]
    try:
        await e.edit(
            f"**Do You Want To Change The Handle Of This Repo?**\n`{repo_name}`",
            parse_mode="md",
            buttons=_proceed_cancel_row(
                proceed_data=f"sh:go:{repo_name}",
                cancel_data="sh:cancel",
            ),
        )
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.CallbackQuery(pattern=rb"^sh:go:"))
@ban_check
async def sh_go_cb(e):
    repo_name = e.data.decode().split("sh:go:", 1)[1]

    sb = SmartButtons()
    sb.button("❌ Cancel", callback_data="sh:cancel")

    try:
        await e.edit(
            "**Send The New Handle For The Repo**\n"
            "Example: `TeleUtilBot` — only the repo name part, not full URL\n"
            "**Click Below Button To Cancel**",
            parse_mode="md",
            buttons=sb.build_menu(b_cols=1),
        )
    except MessageNotModifiedError:
        pass

    await _handle_sessions.put(e.sender_id, {
        "repo":   repo_name,
        "chat":   e.chat_id,
        "msg_id": e.message_id,
    }, ttl=300)

    await e.answer()


@Irene.on(events.CallbackQuery(data=b"sh:cancel"))
@ban_check
async def sh_cancel_cb(e):
    await _handle_sessions.delete(e.sender_id)
    try:
        await e.edit("**Cancelled ❌ Repo Deletation**", parse_mode="md")
    except MessageNotModifiedError:
        pass
    await e.answer()


@Irene.on(events.NewMessage())
@new_task
async def handle_input_router(e):
    if not e.is_private:
        return
    if not e.text:
        return

    s = await _handle_sessions.get(e.sender_id)
    if not s:
        return

    new_handle = e.text.strip()
    repo_name  = s["repo"]
    msg_id     = s["msg_id"]
    chat_id    = s["chat"]

    if chat_id != e.chat_id:
        return

    if not re.match(r"^[a-zA-Z0-9_.\-]+$", new_handle):
        await send_message(
            chat_id,
            "**❌ Invalid handle. Only letters, numbers, `-`, `_`, `.` allowed.**",
            parse_mode="md",
        )
        return

    await _handle_sessions.delete(e.sender_id)

    await edit_message(chat_id, msg_id, "**Changing Repo Handle...**", parse_mode="md")

    api = await _get_api(e.sender_id)
    if not api:
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Handle**", parse_mode="md")
        return

    owner, repo = split_repo(repo_name)
    if not owner or not repo:
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Handle**", parse_mode="md")
        return

    try:
        result       = await api.rename_repo_gh(owner, repo, new_handle)
        new_fullname = result.get("full_name", f"{owner}/{new_handle}")

        try:
            await DataStore.get().rename_repo(repo_name, new_fullname)
        except Exception as ex:
            LOGGER.warning(f"DB rename_repo failed {repo_name} -> {new_fullname}: {ex}")

        new_url = result.get("html_url", f"https://github.com/{new_fullname}")
        sb = SmartButtons()
        sb.button("📥 Repository", url=new_url)

        await edit_message(
            chat_id,
            msg_id,
            f"**✅ Successfully Changed Repo Handle**\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"New Repo: [{new_fullname}]({new_url})",
            parse_mode="md",
            buttons=sb.build_menu(b_cols=1),
            link_preview=False,
        )

    except GhApiError as ex:
        LOGGER.error(f"rename_repo_gh GhApiError {repo_name}: {ex}")
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Handle**", parse_mode="md")
    except Exception as ex:
        LOGGER.error(f"rename_repo_gh error {repo_name}: {ex}")
        await edit_message(chat_id, msg_id, "**Failed To Update Repo Handle**", parse_mode="md")