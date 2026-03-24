from datetime import datetime

from telethon import events

import config
from bot import Irene
from helpers.botutils import send_message
from helpers.logger import LOGGER


def _col():
    from database.store import DataStore
    return DataStore.get()._users


async def upsert_user(user_id: int):
    try:
        now = datetime.utcnow()
        await _col().update_one(
            {"user_id": user_id, "is_group": False},
            {
                "$set": {"user_id": user_id, "last_activity": now, "is_group": False},
                "$inc": {"activity_count": 1},
            },
            upsert=True,
        )
    except Exception as e:
        LOGGER.error(f"upsert_user error {user_id}: {e}")


async def upsert_group(chat_id: int):
    try:
        now = datetime.utcnow()
        await _col().update_one(
            {"user_id": chat_id, "is_group": True},
            {
                "$set": {"user_id": chat_id, "last_activity": now, "is_group": True},
                "$inc": {"activity_count": 1},
            },
            upsert=True,
        )
    except Exception as e:
        LOGGER.error(f"upsert_group error {chat_id}: {e}")


async def remove_group(chat_id: int):
    try:
        await _col().delete_one({"user_id": chat_id, "is_group": True})
        LOGGER.info(f"Removed group {chat_id} from database")
    except Exception as e:
        LOGGER.error(f"remove_group error {chat_id}: {e}")


async def track(sender_id: int, chat_id: int):
    if not sender_id or sender_id < 0:
        return
    await upsert_user(sender_id)
    if chat_id and chat_id != sender_id and chat_id < 0:
        await upsert_group(chat_id)


@Irene.on(events.ChatAction())
async def _on_chat_action(event):
    try:
        me = await Irene.get_me()

        if event.user_added or event.user_joined:
            added_ids = list(getattr(event, "user_ids", None) or [])
            if not added_ids:
                uid = getattr(event, "user_id", None)
                if uid:
                    added_ids = [uid]
            if me.id not in added_ids:
                return

            chat_id = event.chat_id
            await upsert_group(chat_id)

            try:
                chat       = await event.get_chat()
                chat_title = getattr(chat, "title", f"Group {chat_id}")
            except Exception:
                chat_title = f"Group {chat_id}"

            LOGGER.info(f"Bot added to group: {chat_title} ({chat_id})")

            await send_message(
                chat_id,
                f"<b>👋 Thanks for adding me to <b>{chat_title}</b>!</b>\n\n"
                "I'm <b>GitHub Notify Bot ⚙️</b> — your GitHub webhook bridge for Telegram.\n\n"
                "<b>Get Started:</b>\n"
                "1. Use /connect to link your GitHub account <i>(in private chat)</i>\n"
                "2. Use /addrepo to link a repository\n"
                "3. Get real-time notifications for every GitHub event!\n\n"
                f"<b>🔔 Stay updated:</b> <a href='https://{config.UPDATES_URL}'>Join our channel</a>",
                parse_mode="html",
                link_preview=False,
            )

        elif event.user_kicked or event.user_left:
            kicked_ids = list(getattr(event, "user_ids", None) or [])
            if not kicked_ids:
                uid = getattr(event, "user_id", None)
                if uid:
                    kicked_ids = [uid]
            if me.id not in kicked_ids:
                return

            await remove_group(event.chat_id)
            LOGGER.info(f"Bot removed from group {event.chat_id}")

    except Exception as e:
        LOGGER.error(f"_on_chat_action error: {e}")