from telethon import TelegramClient
from telethon.sessions import StringSession

import config
from helpers.logger import LOGGER

Irene = TelegramClient(
    StringSession(),
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    connection_retries=None,
    retry_delay=1,
)


async def start_bot():
    LOGGER.info("Connecting Irene (TelegramClient) via BOT_TOKEN...")
    await Irene.start(bot_token=config.BOT_TOKEN)
    LOGGER.info("Irene connected successfully!")
