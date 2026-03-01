from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ──────────── Local FFmpeg ────────────
# FFmpeg binaries should be placed in <project_root>/ffmpeg/
# Expected structure:
#   ffmpeg/
#     ffmpeg      (or ffmpeg.exe on Windows)
#     ffprobe     (or ffprobe.exe on Windows)
FFMPEG_DIR = BASE_DIR / "ffmpeg"
_ffmpeg_bin = FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
if _ffmpeg_bin.exists():
    # Local ffmpeg found — prepend to PATH
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
    FFMPEG_PATH = str(_ffmpeg_bin)
    FFPROBE_PATH = str(FFMPEG_DIR / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
else:
    # Use system ffmpeg (apt-get install ffmpeg in Docker, or system PATH)
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"


class Settings(BaseSettings):
    # Bot
    bot_token: str = ""
    admin_ids: List[int] = []

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    web_base_url: str = "http://localhost:8080"

    # DB
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'bot.db'}"

    # Subscription
    trial_days: int = 3
    plan_basic_price: int = 99       # Telegram Stars
    plan_basic_downloads: int = 10   # per day
    plan_premium_price: int = 249
    plan_premium_downloads: int = 50
    plan_pro_price: int = 499
    plan_pro_downloads: int = -1     # unlimited

    # Downloads
    max_telegram_file_size: int = 1_990_000_000  # ~1.99 GB
    download_dir: str = str(BASE_DIR / "downloads")
    max_concurrent_downloads: int = 3

    # FFmpeg
    ffmpeg_path: str = FFMPEG_PATH
    ffprobe_path: str = FFPROBE_PATH

    # Security
    secret_key: str = "change-me-in-production"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Union[str, list, int]) -> list:
        """Accept comma-separated string, JSON list, single int, or list."""
        if isinstance(v, list):
            return v
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Try JSON first: "[1,2,3]"
            if v.startswith("["):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            # Comma-separated: "123,456" or single: "123"
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def admin_list(self) -> List[int]:
        return self.admin_ids


settings = Settings()

# Ensure dirs exist
os.makedirs(settings.download_dir, exist_ok=True)
os.makedirs(BASE_DIR / "data", exist_ok=True)
os.makedirs(FFMPEG_DIR, exist_ok=True)
