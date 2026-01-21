import json
from pathlib import Path

# === CONFIG FILE ===
CONFIG_PATH = Path(__file__).parent / "config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    _cfg = json.load(f)

# === DISCORD ===
DISCORD_TOKEN = _cfg.get("DISCORD_TOKEN")
GUILD_ID = int(_cfg.get("GUILD_ID"))

# === MODULES ===
MODULES_CONFIG = _cfg.get("modules", {})

# === CHANNELS ===
POLL_CHANNEL_ID = int(_cfg.get("POLL_CHANNEL_ID", 0))
POLL_MISSING_VOTES_CHANNEL_ID = int(_cfg.get("POLL_MISSING_VOTES_CHANNEL_ID", 0))

# === ROLES ===
ADMIN_ROLE_IDS = _cfg.get("ADMIN_ROLE_IDS", [])
DEFAULT_POLL_NOTIFY_ROLES = _cfg.get("DEFAULT_POLL_NOTIFY_ROLES", [])

# === POLL SETTINGS ===
POLL_NOTIFY_COOLDOWN_SECONDS = _cfg.get("POLL_NOTIFY_COOLDOWN_SECONDS", 600)
