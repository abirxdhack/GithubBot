import asyncio
import os

from helpers.logger import LOGGER


def new_task(func):
    async def wrapper(*args, **kwargs):
        try:
            task = asyncio.create_task(func(*args, **kwargs))
            task.add_done_callback(
                lambda t: t.exception() and LOGGER.error(
                    f"{func.__name__} raised: {t.exception()}"
                )
            )
        except Exception as e:
            LOGGER.error(f"new_task wrapper error in {func.__name__}: {e}")
    return wrapper


def clean_download(*files):
    for path in files:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                LOGGER.info(f"Cleaned temporary file: {path}")
        except Exception as e:
            LOGGER.error(f"clean_download error for {path}: {e}")


def split_repo(full_name: str):
    if "/" not in full_name:
        return None, None
    return full_name.split("/", 1)


def truncate_text(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 4] + "\n..."
