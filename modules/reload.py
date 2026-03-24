import math
import re
import time

from telethon import events
from telethon.tl.types import User

import config
from bot import Irene
from cache.ttlcache import TTLCache
from helpers import send_message, new_task, clean_download
from modules.admins import get_admin_cache

_prefixes   = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_reload_pat = re.compile(rf"^[{_prefixes}]reload(?:\s|$)", re.IGNORECASE)

_rate_limit: TTLCache = TTLCache()


@Irene.on(events.NewMessage(pattern=_reload_pat))
@new_task
async def reload_handler(event):
    chat = await event.get_chat()
    if isinstance(chat, User):
        return

    expiry = await _rate_limit.get(event.chat_id)
    if expiry is not None:
        remaining = expiry - time.monotonic()
        if remaining > 0:
            minutes = math.ceil(remaining / 60)
            await send_message(
                event.chat_id,
                f"Please wait <b>{minutes}</b> minute(s) before reloading again.",
                parse_mode="html",
            )
            return

    try:
        perms = await event.client.get_permissions(event.chat_id, event.sender_id)
        if not (perms.is_admin or perms.is_creator):
            await send_message(event.chat_id, "Only admins can reload the cache.")
            return
    except Exception:
        await send_message(event.chat_id, "Failed to check permissions.")
        return

    admin_cache = get_admin_cache()
    await admin_cache.delete(event.chat_id)

    deadline = time.monotonic() + 600
    await _rate_limit.put(event.chat_id, deadline, ttl=600)

    await send_message(event.chat_id, "✅ Admin cache reloaded.")
