import asyncio
import importlib.util
import signal
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

import config
from bot import Irene, start_bot
from database.store import DataStore
from ghub.hookserver import router as webhook_router
from helpers.logger import LOGGER

HANDLER_DIRS = [
    Path(__file__).parent / "core",
    Path(__file__).parent / "modules",
]


def load_handlers():
    loaded = 0
    for directory in HANDLER_DIRS:
        if not directory.is_dir():
            LOGGER.warning(f"{directory.name}/ not found, skipping...")
            continue
        LOGGER.info(f"Loading handlers from {directory.name}/")
        for path in sorted(directory.glob("*.py")):
            if path.name == "__init__.py":
                continue
            module_name = f"{directory.name}.{path.stem}"
            if module_name in sys.modules:
                LOGGER.info(f"  Already loaded: {module_name}")
                continue
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None:
                    LOGGER.warning(f"  Could not load spec for {module_name}")
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                LOGGER.info(f"  Loaded: {module_name}")
                loaded += 1
            except Exception as e:
                LOGGER.exception(f"  Failed to load {module_name}: {e}")
    LOGGER.info(f"Total handlers loaded: {loaded}")


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_bot_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_task

    LOGGER.info("=" * 62)
    LOGGER.info("  GitHub Notify Bot — Starting Up")
    LOGGER.info("=" * 62)

    store = DataStore.get()
    await store.setup()
    LOGGER.info("Database indexes ready.")

    await start_bot()
    LOGGER.info("Loading handler modules...")
    load_handlers()

    from modules.connect import handle_oauth
    from modules.restart import check_pending_reboot
    app.state.handle_oauth = handle_oauth

    _bot_task = asyncio.create_task(Irene.run_until_disconnected())

    me = await Irene.get_me()
    LOGGER.info(f"Bot ready — @{me.username} (id={me.id})")

    await check_pending_reboot()

    local_ip = _local_ip()
    LOGGER.info(f"Server bound to   : 0.0.0.0:{config.HOOK_PORT}")
    LOGGER.info(f"Local IP          : {local_ip}:{config.HOOK_PORT}")
    LOGGER.info(f"Public URL        : {config.PUBLIC_URL}")
    LOGGER.info(f"Webhook endpoint  : {config.PUBLIC_URL}/webhook/{{token}}")
    LOGGER.info(f"OAuth callback    : {config.PUBLIC_URL}/auth/callback")
    LOGGER.info("Bot is now running and listening for events...")

    yield

    LOGGER.info("Stop Signal Received!  Shutting Down Bot & Api...")

    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass

    if Irene.is_connected():
        await Irene.disconnect()

    LOGGER.info("Bot & API stopped cleanly.")


app = FastAPI(
    title="GitHub Notify Bot",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.include_router(webhook_router)


def _handle_signal(sig, frame):
    LOGGER.info("Stop Signal Received!  Shutting Down Bot & Api...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        server_cfg = uvicorn.Config(
            app="main:app",
            host="0.0.0.0",
            port=config.HOOK_PORT,
            loop="uvloop",
            log_level="error",
            access_log=False,
        )
        uvicorn.Server(server_cfg).run()
    except KeyboardInterrupt:
        LOGGER.info("Stop Signal Received!  Shutting Down Bot & Api...")
        sys.exit(0)
    except SystemExit:
        pass
    except Exception as e:
        LOGGER.exception(f"Fatal error: {e}")
        sys.exit(1)
