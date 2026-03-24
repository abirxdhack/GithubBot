import asyncio
from datetime import datetime, timedelta

from telethon import events

import config
from bot import Irene
from database.store import DataStore
from helpers import LOGGER, send_message, SmartButtons, get_args, new_task
from helpers.guard import admin_only


def _pfx(cmds):
    esc    = "".join(c if c.isalpha() else f"\\{c}" for c in config.COMMAND_PREFIXES)
    joined = "|".join(cmds)
    return rf"^[{esc}]({joined})(?:\s|$)"


@Irene.on(events.NewMessage(pattern=_pfx(["stats", "report", "status"])))
@admin_only
@new_task
async def stats_handler(event):
    try:
        store   = DataStore.get()
        now     = datetime.utcnow()
        daily   = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
        weekly  = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
        monthly = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
        yearly  = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
        total_users  = await store.count_users({"is_group": False})
        total_groups = await store.count_users({"is_group": True})

        sb = SmartButtons()
        sb.button(text="Updates Channel", url=f"https://{config.UPDATES_URL}")

        await send_message(
            event.chat_id,
            (
                "<b>📊 GitHub Notify Bot Status ⇾ Report ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                "<b>Users & Groups Engagement:</b>\n"
                f"<b>1 Day:</b> {daily} users were active\n"
                f"<b>1 Week:</b> {weekly} users were active\n"
                f"<b>1 Month:</b> {monthly} users were active\n"
                f"<b>1 Year:</b> {yearly} users were active\n"
                f"<b>Total Connected Groups:</b> {total_groups}\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Total Bot Users:</b> {total_users} ✅"
            ),
            parse_mode="html",
            buttons=sb.build_menu(b_cols=1),
        )
        LOGGER.info("Stats command completed")
    except Exception as e:
        LOGGER.error(f"stats_handler error: {e}")
        await send_message(event.chat_id, "<b>Sorry Database Client Unavailable ❌</b>", parse_mode="html")


@Irene.on(events.NewMessage(pattern=_pfx(["broadcast", "send"])))
@admin_only
@new_task
async def broadcast_handler(event):
    if not event.is_reply:
        await send_message(event.chat_id, "<b>Please reply to a message to broadcast it.</b>", parse_mode="html")
        return

    replied = await event.get_reply_message()
    if not replied:
        await send_message(event.chat_id, "<b>Could not find the replied message.</b>", parse_mode="html")
        return

    text = event.message.text or ""
    cmd  = text.lstrip("".join(config.COMMAND_PREFIXES)).split()[0].lower() if text else "broadcast"
    await _process_broadcast(replied, cmd == "broadcast", event.chat_id)


async def _process_broadcast(content, is_broadcast: bool, origin_chat_id: int):
    try:
        processing_msg = await send_message(origin_chat_id, "<b>Broadcasting Your Message To Users...</b>", parse_mode="html")

        store    = DataStore.get()
        all_ids  = await store.all_user_ids()
        user_ids = [c["user_id"] for c in all_ids if not c.get("is_group", False)]
        grp_ids  = [c["user_id"] for c in all_ids if c.get("is_group", False)]

        LOGGER.info(f"Broadcasting to {len(user_ids)} users and {len(grp_ids)} groups")

        sb = SmartButtons()
        sb.button(text="Updates Channel", url=f"https://{config.UPDATES_URL}")
        buttons = sb.build_menu(b_cols=1)

        succ_users = blocked = succ_grps = fail_grps = 0
        all_targets = [(uid, False) for uid in user_ids] + [(gid, True) for gid in grp_ids]

        async def _send_one(target_id, is_group):
            try:
                if is_broadcast:
                    await Irene.forward_messages(target_id, content)
                else:
                    await Irene.forward_messages(target_id, content, drop_author=True)
                return "group" if is_group else "user", "success"
            except Exception as ex:
                LOGGER.warning(f"Failed to send to {target_id}: {ex}")
                return "group" if is_group else "user", "blocked" if not is_group else "failed"

        for i in range(0, len(all_targets), 30):
            batch   = all_targets[i:i + 30]
            results = await asyncio.gather(*[_send_one(tid, ig) for tid, ig in batch], return_exceptions=True)
            for result in results:
                if isinstance(result, tuple):
                    chat_type, status = result
                    if chat_type == "user":
                        succ_users += 1 if status == "success" else 0
                        blocked    += 1 if status != "success" else 0
                    else:
                        succ_grps += 1 if status == "success" else 0
                        fail_grps += 1 if status != "success" else 0
            await asyncio.sleep(1)

        if processing_msg:
            await Irene.delete_messages(origin_chat_id, processing_msg.id)

        await send_message(
            origin_chat_id,
            (
                "<b>GitHub Notify Bot Broadcast Successful ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ To Users:</b> {succ_users} Users\n"
                f"<b>⊗ Blocked Users:</b> {blocked} Users\n"
                f"<b>⊗ To Groups:</b> {succ_grps} Groups\n"
                f"<b>⊗ Failed Groups:</b> {fail_grps} Groups\n"
                f"<b>⊗ Total Chats:</b> {succ_users + succ_grps} Chats\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smooth Telecast → Activated ✅</b>"
            ),
            parse_mode="html",
            buttons=buttons,
        )
    except Exception as e:
        LOGGER.error(f"_process_broadcast error: {e}")
        await send_message(origin_chat_id, "<b>Sorry Broadcast Send Failed ❌</b>", parse_mode="html")


@Irene.on(events.NewMessage(pattern=_pfx(["ban"])))
@admin_only
@new_task
async def ban_handler(event):
    args    = get_args(event.message)
    replied = await event.get_reply_message() if event.is_reply else None

    target_id = None
    full_name = None
    reason    = "undefined"

    if replied and replied.sender:
        target_id = replied.sender_id
        s         = replied.sender
        full_name = f"{s.first_name or ''} {getattr(s, 'last_name', '') or ''}".strip() or str(target_id)
        if args:
            reason = " ".join(args)
    elif args:
        try:
            identifier = args[0]
            if len(args) > 1:
                reason = " ".join(args[1:])
            entity    = await Irene.get_entity(identifier if identifier.startswith("@") else int(identifier))
            target_id = entity.id
            full_name = f"{entity.first_name or ''} {getattr(entity, 'last_name', '') or ''}".strip() or str(target_id)
        except Exception as e:
            LOGGER.error(f"Failed to resolve ban user: {e}")
            await send_message(event.chat_id, "<b>Please Provide A Valid User To Ban ❌</b>", parse_mode="html")
            return

    if not target_id:
        await send_message(event.chat_id, "<b>Please Provide A Valid User To Ban ❌</b>", parse_mode="html")
        return

    if target_id == config.ADMIN_ID:
        await send_message(event.chat_id, "<b>Lol I Can Not Ban My Creator ❌</b>", parse_mode="html")
        return

    store = DataStore.get()
    if await store.is_banned(target_id):
        await send_message(event.chat_id, "<b>User Is Already Banned ❌</b>", parse_mode="html")
        return

    prog = await send_message(event.chat_id, "<b>Banning User From Bot...</b>", parse_mode="html")
    await asyncio.sleep(1)

    ban_date = datetime.utcnow()
    await store.ban_user(target_id, {
        "user_id":   target_id,
        "full_name": full_name,
        "ban_date":  ban_date,
        "reason":    reason,
    })

    await Irene.edit_message(
        event.chat_id, prog,
        f"<b>{full_name} [<code>{target_id}</code>] banned.</b>\n"
        f"<b>Reason:</b> {reason}\n"
        f"<b>Ban Date:</b> {ban_date.strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="html",
    )


@Irene.on(events.NewMessage(pattern=_pfx(["unban"])))
@admin_only
@new_task
async def unban_handler(event):
    args    = get_args(event.message)
    replied = await event.get_reply_message() if event.is_reply else None

    target_id = None
    full_name = None

    if replied and replied.sender:
        target_id = replied.sender_id
        s         = replied.sender
        full_name = f"{s.first_name or ''} {getattr(s, 'last_name', '') or ''}".strip() or str(target_id)
    elif args:
        try:
            identifier = args[0]
            entity    = await Irene.get_entity(identifier if identifier.startswith("@") else int(identifier))
            target_id = entity.id
            full_name = f"{entity.first_name or ''} {getattr(entity, 'last_name', '') or ''}".strip() or str(target_id)
        except Exception as e:
            LOGGER.error(f"Failed to resolve unban user: {e}")
            await send_message(event.chat_id, "<b>Please Provide A Valid User To Unban ❌</b>", parse_mode="html")
            return

    if not target_id:
        await send_message(event.chat_id, "<b>Please Provide A Valid User To Unban ❌</b>", parse_mode="html")
        return

    store   = DataStore.get()
    prog    = await send_message(event.chat_id, "<b>Unbanning User From Bot...</b>", parse_mode="html")
    await asyncio.sleep(1)

    if not await store.is_banned(target_id):
        await Irene.edit_message(event.chat_id, prog, "<b>User Is Not Banned ❌</b>", parse_mode="html")
        return

    removed      = await store.unban_user(target_id)
    profile_link = f"tg://user?id={target_id}"

    if removed:
        await Irene.edit_message(
            event.chat_id, prog,
            f"<b>✅ Successfully Unbanned <a href='{profile_link}'>{full_name}</a>!</b>",
            parse_mode="html",
        )
        await send_message(target_id, "<b>Good News, You Can Now Use Me ✅</b>", parse_mode="html")
    else:
        await Irene.edit_message(event.chat_id, prog, "<b>❌ Failed to unban user!</b>", parse_mode="html")


@Irene.on(events.NewMessage(pattern=_pfx(["banlist"])))
@admin_only
@new_task
async def banlist_handler(event):
    prog = await send_message(event.chat_id, "<b>Fetching Banned List From Database...</b>", parse_mode="html")
    await asyncio.sleep(1)

    store       = DataStore.get()
    banned_list = await store.get_banlist()

    if not banned_list:
        await Irene.edit_message(event.chat_id, prog, "<b>No Users Are Currently Banned ✅</b>", parse_mode="html")
        return

    lines = ["<b>🚫 Banned Users List:</b>", "<b>━━━━━━━━━━━━━━━━━</b>"]
    for i, user in enumerate(banned_list, 1):
        bd     = user.get("ban_date", datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
        reason = user.get("reason", "Undefined")
        lines += [
            f"<b>{i}. {user['full_name']} [<code>{user['user_id']}</code>]</b>",
            f"<b>⊗ Reason:</b> {reason}",
            f"<b>⊗ Ban Date:</b> {bd}",
            "<b>━━━━━━━━━━━━━━━━━</b>",
        ]
    lines.append(f"<b>Total Banned Users: {len(banned_list)} ✅</b>")

    sb = SmartButtons()
    sb.button(text="✘ Close", callback_data="close_banlist", position="footer")

    await Irene.edit_message(event.chat_id, prog, "\n".join(lines), parse_mode="html", buttons=sb.build_menu(b_cols=1, f_cols=1))


@Irene.on(events.CallbackQuery(data=b"close_banlist"))
async def close_banlist_cb(event):
    sender = await event.get_sender()
    store  = DataStore.get()
    guards = await store.get_guards()
    if sender.id != config.ADMIN_ID and sender.id not in [g["user_id"] for g in guards]:
        return
    try:
        await event.delete()
    except Exception as e:
        LOGGER.error(f"close_banlist_cb error: {e}")
