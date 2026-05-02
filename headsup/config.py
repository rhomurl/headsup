import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    default_tz: str
    db_path: str
    admin_chat_id: int | None
    log_level: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
    admin_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    return Config(
        bot_token=token,
        default_tz=os.getenv("DEFAULT_TZ", "Asia/Manila").strip() or "Asia/Manila",
        db_path=os.getenv("DB_PATH", "headsup.db").strip() or "headsup.db",
        admin_chat_id=int(admin_raw) if admin_raw else None,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
