import asyncio
import os
import shutil
import subprocess

from telethon import events

import config
from bot import Irene
from database.store import DataStore
from helpers import LOGGER, send_message, new_task
from helpers.guard import admin_only


def _pfx(cmds):
    esc    = "".join(c if c.isalpha() else f"\\{c}" for c in config.COMMAND_PREFIXES)
    joined = "|".join(cmds)
    return rf"^[{esc}]({joined})(?:\s|$)"


async def _cleanup_dirs():
    directories = ["downloads", "temp", "temp_media", "data"]
    for directory in directories:
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                LOGGER.info(f"Cleared directory: {directory}")
        except Exception as e:
            LOGGER.error(f"Failed to clear directory {directory}: {e}")


async def _do_restart(chat_id: int, msg_id: int):
    await _cleanup_dirs()

    store = DataStore.get()
    await store.save_reboot(chat_id, msg_id)

    await asyncio.sleep(2)

    try:
        await Irene.disconnect()
        LOGGER.info("Irene disconnected for restart")
    except Exception as e:
        LOGGER.error(f"Error disconnecting Irene: {e}")

    try:
        start_script = "start.sh"
        if os.path.exists(start_script) and os.access(start_script, os.X_OK):
            subprocess.Popen(["bash", start_script], stdin=subprocess.DEVNULL, start_new_session=True, cwd=os.getcwd())
            LOGGER.info("Restart launched via start.sh")
        else:
            subprocess.Popen(["python3", "main.py"], stdin=subprocess.DEVNULL, start_new_session=True, cwd=os.getcwd())
            LOGGER.info("Restart launched via python3 main.py")
    except Exception as e:
        LOGGER.error(f"Failed to launch restart process: {e}")

    await asyncio.sleep(2)
    os._exit(0)


@Irene.on(events.NewMessage(pattern=_pfx(["restart", "reboot"])))
@admin_only
@new_task
async def restart_handler(event):
    try:
        prog = await send_message(event.chat_id, "<b>Restarting Bot... Please Wait.</b>", parse_mode="html")
        if prog:
            asyncio.get_event_loop().create_task(_do_restart(event.chat_id, prog.id))
            LOGGER.info(f"Restart initiated by user_id {event.sender_id}")
        else:
            await send_message(event.chat_id, "<b>Failed to initiate restart!</b>", parse_mode="html")
    except Exception as e:
        LOGGER.error(f"restart_handler error: {e}")


@Irene.on(events.NewMessage(pattern=_pfx(["stop", "kill"])))
@admin_only
@new_task
async def stop_handler(event):
    try:
        prog = await send_message(event.chat_id, "<b>Stopping bot and clearing data...</b>", parse_mode="html")
        await _cleanup_dirs()

        store = DataStore.get()
        await store.clear_reboot()

        if prog:
            try:
                await Irene.edit_message(event.chat_id, prog, "<b>Bot stopped successfully ✅</b>", parse_mode="html")
            except Exception:
                pass

        await asyncio.sleep(2)

        try:
            await Irene.disconnect()
            LOGGER.info("Irene disconnected for stop")
        except Exception as e:
            LOGGER.error(f"Error disconnecting Irene: {e}")

        os._exit(0)
    except Exception as e:
        LOGGER.error(f"stop_handler error: {e}")
        os._exit(1)


async def check_pending_reboot():
    store  = DataStore.get()
    reboot = await store.get_reboot()
    if not reboot:
        return
    await store.clear_reboot()
    try:
        await Irene.edit_message(
            reboot["chat_id"], reboot["msg_id"],
            "<b>Bot Restarted Successfully ✅</b>",
            parse_mode="html",
        )
        LOGGER.info(f"Notified reboot completion to chat {reboot['chat_id']}")
    except Exception as e:
        LOGGER.error(f"check_pending_reboot notify error: {e}")
