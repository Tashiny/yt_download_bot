"""
Video download service using yt-dlp.
Handles YouTube and TikTok downloads with quality selection.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

import yt_dlp

from config import settings


async def download_video(
    url: str,
    format_id: str = "best",
    platform: str = "youtube",
    output_dir: Optional[str] = None,
) -> Path:
    """
    Download video and return path to the downloaded file.
    For TikTok, downloads without watermark.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _download_sync, url, format_id, platform, output_dir
    )


def _download_sync(
    url: str,
    format_id: str,
    platform: str,
    output_dir: Optional[str],
) -> Path:
    """Synchronous download."""
    if output_dir is None:
        output_dir = settings.download_dir

    file_id = uuid.uuid4().hex[:12]
    output_template = os.path.join(output_dir, f"{file_id}_%(title).50s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "postprocessors": [],
    }

    # Only set ffmpeg_location if it's an actual path (not just "ffmpeg")
    _ffmpeg_dir = str(Path(settings.ffmpeg_path).parent)
    if Path(settings.ffmpeg_path).is_absolute() and Path(settings.ffmpeg_path).exists():
        ydl_opts["ffmpeg_location"] = _ffmpeg_dir

    # Use cookies file if it exists (bypass YouTube bot detection)
    if Path(settings.cookies_file).exists():
        ydl_opts["cookiefile"] = settings.cookies_file

    if platform == "tiktok":
        # TikTok: download best quality without watermark
        ydl_opts["format"] = "best"
    else:
        # YouTube: use format_id or merge best video+audio
        if format_id and format_id != "best":
            ydl_opts["format"] = f"{format_id}+bestaudio[ext=m4a]/{format_id}+bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    ydl_opts["postprocessors"].append({
        "key": "FFmpegVideoConvertor",
        "preferedformat": "mp4",
    })

    downloaded_file = None

    class FilenameCollector:
        def __init__(self):
            self.filenames = []

    collector = FilenameCollector()

    def progress_hook(d):
        if d["status"] == "finished":
            collector.filenames.append(d.get("filename", ""))

    ydl_opts["progress_hooks"] = [progress_hook]

    # Try default client first, fall back to mobile clients on sign-in error
    for attempt, client_config in enumerate([
        None,  # attempt 0: default
        {"youtube": {"player_client": ["android_creator", "android", "ios"]}},  # attempt 1
        {"youtube": {"player_client": ["mweb"]}},  # attempt 2: last resort
    ]):
        try:
            opts = dict(ydl_opts)
            if client_config:
                opts["extractor_args"] = client_config
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            break
        except Exception as e:
            err_msg = str(e).lower()
            if "sign in" in err_msg or "bot" in err_msg or "confirm" in err_msg:
                if attempt < 2:
                    collector.filenames.clear()
                    continue
            raise

    # Find the downloaded file
    if collector.filenames:
        # The last finished file
        candidate = collector.filenames[-1]
        # Check if mp4 version exists (from post-processing)
        mp4_path = Path(candidate).with_suffix(".mp4")
        if mp4_path.exists():
            downloaded_file = mp4_path
        elif Path(candidate).exists():
            downloaded_file = Path(candidate)

    if downloaded_file is None:
        # Fallback: find newest file in output_dir with our file_id
        candidates = list(Path(output_dir).glob(f"{file_id}_*"))
        if candidates:
            downloaded_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if downloaded_file is None or not downloaded_file.exists():
        raise FileNotFoundError("Не удалось найти загруженный файл")

    return downloaded_file


def cleanup_file(file_path: Path) -> None:
    """Remove a downloaded file."""
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        pass


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    return file_path.stat().st_size if file_path.exists() else 0
