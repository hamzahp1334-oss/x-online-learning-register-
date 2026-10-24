"""Configuration for Online Quran Academy Telegram Bots."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
def load_dotenv():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                os.environ.setdefault(k, v)

load_dotenv()

# Tokens
DEFAULT_TOKEN = "8594518638:AAFxCnlFmhNZhwc-tLKA1rjWBhIaAhoeHe8"
STUDENT_BOT_TOKEN = (
    os.environ.get("STUDENT_BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or DEFAULT_TOKEN
).strip()

ADMIN_BOT_TOKEN = (
    os.environ.get("ADMIN_BOT_TOKEN")
    or STUDENT_BOT_TOKEN
).strip()

# Mode: unified (same token for both) vs separate (two distinct tokens)
IS_UNIFIED_MODE = (STUDENT_BOT_TOKEN == ADMIN_BOT_TOKEN)

# Authorized Telegram admin user IDs (comma-separated list in env)
DEFAULT_ADMIN_IDS = [6666443909, 8053250308]
_admin_ids_raw = os.environ.get("ADMIN_TELEGRAM_IDS", "6666443909,8053250308")
ADMIN_TELEGRAM_IDS = list(DEFAULT_ADMIN_IDS)
for _part in _admin_ids_raw.split(","):
    _part = _part.strip()
    if _part.isdigit():
        val = int(_part)
        if val not in ADMIN_TELEGRAM_IDS:
            ADMIN_TELEGRAM_IDS.append(val)

# Public website base URL if configured (for meeting links or portal)
ACADEMY_WEB_URL = os.environ.get("ACADEMY_WEB_URL", "http://localhost:3000").rstrip("/")
