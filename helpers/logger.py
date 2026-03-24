import logging

_fmt = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(_fmt)

_file = logging.FileHandler("botlog.txt", encoding="utf-8")
_file.setLevel(logging.INFO)
_file.setFormatter(_fmt)

logging.basicConfig(handlers=[_console, _file], level=logging.INFO)

for _name in ("telethon", "telethon.client", "telethon.network",
              "telethon.extensions", "telethon.sessions",
              "uvicorn", "uvicorn.access", "fastapi"):
    logging.getLogger(_name).setLevel(logging.ERROR)

LOGGER = logging.getLogger(__name__)
LOGGER.info("Creating Logger For Logging...")
LOGGER.info("Logger Successfully Created & Initialized")
