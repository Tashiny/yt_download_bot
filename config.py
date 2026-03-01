from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ──────────── Local FFmpeg ────────────
# FFmpeg binaries should be placed in <project_root>/ffmpeg/
# Expected structure:
#   ffmpeg/
#     ffmpeg.exe
#     ffprobe.exe
FFMPEG_DIR = BASE_DIR / "ffmpeg"
if FFMPEG_DIR.exists():
    # Prepend to PATH so yt-dlp and any subprocess finds it first
    os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
    FFMPEG_PATH = str(FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    FFPROBE_PATH = str(FFMPEG_DIR / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
else:
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
