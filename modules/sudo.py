import asyncio
from datetime import datetime

from telethon import events

import config
from bot import Irene
from database.store import DataStore
from helpers import LOGGER, send_message, SmartButtons, get_args
from helpers.guard import admin_only


def _pfx(cmds):
    esc    = "".join(c if c.isalpha() else f"\\{c}" for c in config.COMMAND_PREFIXES)
    joined = "|".join(cmds)
    return rf"^[{esc}]({joined})(?:\s|$)"


async def _resolve_user(identifier: str):
    try:
        entity    = await Irene.get_entity(identifier if identifier.startswith("@") else int(identifier))
        full_name = f"{entity.first_name or ''} {getattr(entity, 'last_name', '') or ''}".strip() or str(entity.id)
        username  = f"@{entity.username}" if getattr(entity, "username", None) else "None"
        return entity.id, full_name, username
    except Exception as e:
        LOGGER.error(f"_resolve_user error for {identifier}: {e}")
        return None, None, None


@Irene.on(events.NewMessage(pattern=_pfx(["getadmins"])))
async def getadmins_handler(event):
    sender = await event.get_sender()
    if sender.id != config.ADMIN_ID:
        return

    store = DataStore.get()
    prog  = await send_message(event.chat_id, "<b>Fetching GitHub Bot Admins List...</b>", parse_mode="html")
    await asyncio.sleep(0.5)

    lines = ["<b>GitHub Notify Bot Admins List ✅</b>", "<b>━━━━━━━━━━━━━━━━━</b>"]

    try:
        owner      = await Irene.get_entity(config.ADMIN_ID)
        owner_name = f"{owner.first_name or ''} {getattr(owner, 'last_name', '') or ''}".strip()
        owner_link = f"tg://user?id={config.ADMIN_ID}"
        lines += [
            f"<b>⊗ Name:</b> <a href='{owner_link}'>{owner_name}</a>",
            "<b>⊗ Title:</b> Owner",
            f"<b>⊗ User ID:</b> <code>{config.ADMIN_ID}</code>",
            "<b>⊗ Auth Date:</b> Infinity",
            "<b>⊗ Auth By:</b> Creator",
            "<b>━━━━━━━━━━━━━━━━━</b>",
        ]
    except Exception as e:
        LOGGER.error(f"Could not fetch owner entity: {e}")

    auth_admins = await store.get_guards()
    total       = 1 + len(auth_admins)

    for admin in auth_admins:
        uid = admin["user_id"]
        try:
            u     = await Irene.get_entity(uid)
            fname = f"{u.first_name or ''} {getattr(u, 'last_name', '') or ''}".strip()
        except Exception:
            fname = admin.get("full_name", f"User_{uid}")

        link      = f"tg://user?id={uid}"
        auth_time = admin.get("auth_time", datetime.utcnow())
        lines += [
            f"<b>⊗ Name:</b> <a href='{link}'>{fname}</a>",
            f"<b>⊗ Title:</b> {admin.get('title', 'Admin')}",
            f"<b>⊗ User ID:</b> <code>{uid}</code>",
            f"<b>⊗ Auth Time:</b> {auth_time.strftime('%H:%M:%S')}",
            f"<b>⊗ Auth Date:</b> {auth_time.strftime('%Y-%m-%d')}",
            f"<b>⊗ Auth By:</b> {admin.get('auth_by', 'Unknown')}",
            "<b>━━━━━━━━━━━━━━━━━</b>",
        ]

    lines.append(f"<b>Total GitHub Bot Admins: {total} ✅</b>")

    sb = SmartButtons()
    sb.button(text="✘ Close", callback_data="sudo_close_admins")

    try:
        await Irene.edit_message(
            event.chat_id, prog.id, "\n".join(lines),
            parse_mode="html", buttons=sb.build_menu(b_cols=1)
        )
    except Exception as e:
        LOGGER.error(f"getadmins edit error: {e}")
        await send_message(event.chat_id, "<b>❌ Failed to display admin list!</b>", parse_mode="html")


@Irene.on(events.NewMessage(pattern=_pfx(["auth"])))
async def auth_handler(event):
    sender = await event.get_sender()
    if sender.id != config.ADMIN_ID:
        return

    args = get_args(event.message)
    if not args:
        await send_message(event.chat_id, "<b>❌ Usage: /auth @user [Title]</b>", parse_mode="html")
        return

    identifier        = args[0]
    title             = args[1] if len(args) > 1 else "Admin"
    target_id, full_name, username = await _resolve_user(identifier)

    if not target_id:
        await send_message(event.chat_id, "<b>❌ Could not resolve user!</b>", parse_mode="html")
        return
    if target_id == config.ADMIN_ID:
        await send_message(event.chat_id, "<b>This User Is Already The Owner ❌</b>", parse_mode="html")
        return

    store       = DataStore.get()
    auth_admins = await store.get_guards()
    if any(a["user_id"] == target_id for a in auth_admins):
        await send_message(event.chat_id, "<b>This User Is Already One Of The Staff ❌</b>", parse_mode="html")
        return

    prog = await send_message(event.chat_id, "<b>Promoting user to authorized users...</b>", parse_mode="html")
    await asyncio.sleep(0.5)

    try:
        owner   = await Irene.get_entity(config.ADMIN_ID)
        auth_by = f"{owner.first_name or ''} {getattr(owner, 'last_name', '') or ''}".strip()
    except Exception:
        auth_by = str(config.ADMIN_ID)

    now = datetime.utcnow()
    await store.add_guard(target_id, {
        "user_id":   target_id,
        "title":     title,
        "username":  username,
        "full_name": full_name,
        "auth_by":   auth_by,
        "auth_time": now,
        "auth_date": now,
    })

    profile_link = f"tg://user?id={target_id}"
    await Irene.edit_message(
        event.chat_id, prog.id,
        f"<b>✅ Successfully promoted <a href='{profile_link}'>{full_name}</a> as {title}!</b>",
        parse_mode="html",
    )


@Irene.on(events.NewMessage(pattern=_pfx(["unauth"])))
async def unauth_handler(event):
    sender = await event.get_sender()
    if sender.id != config.ADMIN_ID:
        return

    args = get_args(event.message)
    if not args:
        await send_message(event.chat_id, "<b>❌ Usage: /unauth @user</b>", parse_mode="html")
        return

    target_id, full_name, _ = await _resolve_user(args[0])
    if not target_id:
        await send_message(event.chat_id, "<b>❌ Could not resolve user!</b>", parse_mode="html")
        return
    if target_id == config.ADMIN_ID:
        await send_message(event.chat_id, "<b>I Can Not Unauthorize My Creator ❌</b>", parse_mode="html")
        return

    store   = DataStore.get()
    prog    = await send_message(event.chat_id, "<b>Demoting user from authorized users...</b>", parse_mode="html")
    await asyncio.sleep(0.5)

    removed      = await store.remove_guard(target_id)
    profile_link = f"tg://user?id={target_id}"

    if removed:
        await Irene.edit_message(
            event.chat_id, prog.id,
            f"<b>✅ Successfully demoted <a href='{profile_link}'>{full_name}</a>!</b>",
            parse_mode="html",
        )
    else:
        await Irene.edit_message(
            event.chat_id, prog.id,
            "<b>❌ User not found in admin list!</b>",
            parse_mode="html",
        )


@Irene.on(events.CallbackQuery(data=b"sudo_close_admins"))
async def close_admins_cb(event):
    sender = await event.get_sender()
    if sender.id != config.ADMIN_ID:
        return
    try:
        await event.delete()
    except Exception as e:
        LOGGER.error(f"close_admins_cb error: {e}")
        await event.answer("❌ Failed to close!", alert=True)