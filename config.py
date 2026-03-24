import os
from dotenv import load_dotenv

load_dotenv()

API_ID           = int(os.environ.get("API_ID", "0"))
API_HASH         = os.environ.get("API_HASH", "")
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
MONGO_URI        = os.environ.get("MONGO_URI", "")
DB_NAME          = os.environ.get("DB_NAME", "")
GH_CLIENT_ID     = os.environ.get("GH_CLIENT_ID", "")
GH_CLIENT_SECRET = os.environ.get("GH_CLIENT_SECRET", "")
HOOK_SECRET      = os.environ.get("HOOK_SECRET", "")
PUBLIC_URL       = os.environ.get("PUBLIC_URL", "").rstrip("/")
CIPHER_KEY       = os.environ.get("CIPHER_KEY", "")
HOOK_PORT        = int(os.environ.get("HOOK_PORT", "0"))
UPDATES_URL      = os.environ.get("UPDATES_URL", "")
ADMIN_ID         = int(os.environ.get("ADMIN_ID", "0"))
COMMAND_PREFIXES = ["/", "!", ".", ","]