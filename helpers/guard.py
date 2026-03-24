import functools

from helpers.logger import LOGGER


def admin_only(func):
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        from config import ADMIN_ID
        from database.store import DataStore
        try:
            sender = await event.get_sender()
            user_id = sender.id
        except Exception:
            return
        try:
            guards = await DataStore.get().get_guards()
            auth_ids = [g["user_id"] for g in guards]
        except Exception:
            auth_ids = []
        if user_id != ADMIN_ID and user_id not in auth_ids:
            LOGGER.info(f"Unauthorized access attempt by user_id {user_id}")
            return
        return await func(event, *args, **kwargs)
    return wrapper


def ban_check(func):
    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        from database.store import DataStore
        try:
            sender = await event.get_sender()
            if sender is None:
                return
            user_id = sender.id
        except Exception:
            return
        try:
            if await DataStore.get().is_banned(user_id):
                LOGGER.info(f"Banned user {user_id} tried to use bot — silently ignored")
                return
        except Exception as e:
            LOGGER.error(f"ban_check DB error for {user_id}: {e}")
        return await func(event, *args, **kwargs)
    return wrapper
