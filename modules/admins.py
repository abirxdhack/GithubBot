import logging

from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsAdmins, Channel, Chat

from bot import Irene
from cache.ttlcache import TTLCache

logger = logging.getLogger(__name__)

_admin_cache: TTLCache = TTLCache()


def get_admin_cache() -> TTLCache:
    return _admin_cache


async def is_admin(chat_id: int, user_id: int) -> bool:
    cached = await _admin_cache.get(chat_id)
    if cached is not None:
        return user_id in cached
    try:
        entity = await Irene.get_entity(chat_id)
        if isinstance(entity, Channel):
            result = await Irene(GetParticipantsRequest(
                channel=entity,
                filter=ChannelParticipantsAdmins(),
                offset=0,
                limit=200,
                hash=0,
            ))
            admin_ids = [u.id for u in result.users]
            await _admin_cache.put(chat_id, admin_ids, ttl=300)
            return user_id in admin_ids
        elif isinstance(entity, Chat):
            perms = await Irene.get_permissions(chat_id, user_id)
            return perms.is_admin or perms.is_creator
        return False
    except Exception as exc:
        logger.warning(f"is_admin fallback — chat={chat_id} user={user_id}: {exc}")
        try:
            perms = await Irene.get_permissions(chat_id, user_id)
            return perms.is_admin or perms.is_creator
        except Exception:
            return False
