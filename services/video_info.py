"""
Service for extracting video information (formats, sizes, qualities)
from YouTube and TikTok using yt-dlp.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yt_dlp

from config import settings


@dataclass
class VideoFormat:
    """Represents a single downloadable video format."""
    format_id: str
    quality_label: str      # e.g. "1080p", "720p", "480p"
    height: int
    ext: str
    file_size: Optional[int]  # bytes, may be estimated
    has_audio: bool
    fps: Optional[int] = None
    vcodec: str = ""
    acodec: str = ""

    @property
    def size_mb(self) -> float:
        if self.file_size:
            return self.file_size / (1024 * 1024)
        return 0.0

    @property
    def size_display(self) -> str:
        if not self.file_size:
            return "~неизвестно"
        mb = self.size_mb
        if mb >= 1024:
            return f"{mb / 1024:.1f} ГБ"
        return f"{mb:.0f} МБ"


@dataclass
class VideoInfo:
    """Complete info about a video."""
    url: str
    title: str
    duration: int                   # seconds
    thumbnail: Optional[str]
    platform: str                   # youtube / tiktok
    uploader: str
    formats: List[VideoFormat] = field(default_factory=list)

    @property
    def duration_display(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


def detect_platform(url: str) -> Optional[str]:
    """Detect platform from URL."""
    url_lower = url.lower()
    if any(x in url_lower for x in ["youtube.com", "youtu.be"]):
        return "youtube"
    if any(x in url_lower for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]):
        return "tiktok"
    return None


def is_valid_url(text: str) -> bool:
    """Check if text contains a valid YouTube or TikTok URL."""
    pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|([a-z]{2,3}\.)?tiktok\.com)/\S+'
    return bool(re.search(pattern, text))


def extract_url(text: str) -> Optional[str]:
    """Extract first valid URL from text."""
    pattern = r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be|(?:[a-z]{2,3}\.)?tiktok\.com)/\S+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None


async def get_video_info(url: str) -> VideoInfo:
    """
    Extract video info and available formats.
    Returns VideoInfo with sorted formats (highest quality first).
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_info_sync, url)


def _extract_info_sync(url: str) -> VideoInfo:
    """Synchronous video info extraction."""
    platform = detect_platform(url) or "unknown"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "no_color": True,
    }

    # Only set ffmpeg_location if it's an actual existing path
    if Path(settings.ffmpeg_path).is_absolute() and Path(settings.ffmpeg_path).exists():
        ydl_opts["ffmpeg_location"] = str(Path(settings.ffmpeg_path).parent)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("Не удалось получить информацию о видео")

    title = info.get("title", "Без названия")
    duration = info.get("duration", 0) or 0
    thumbnail = info.get("thumbnail")
    uploader = info.get("uploader", info.get("channel", "Неизвестно"))

    # Process formats
    raw_formats = info.get("formats", [])
    formats_map: dict[int, VideoFormat] = {}

    for fmt in raw_formats:
        height = fmt.get("height")
        if not height or height < 144:
            continue

        vcodec = fmt.get("vcodec", "none")
        acodec = fmt.get("acodec", "none")

        # Skip audio-only
        if vcodec == "none":
            continue

        file_size = fmt.get("filesize") or fmt.get("filesize_approx")

        # For combined formats (video+audio)
        has_audio = acodec != "none"

        fmt_obj = VideoFormat(
            format_id=fmt.get("format_id", ""),
            quality_label=f"{height}p",
            height=height,
            ext=fmt.get("ext", "mp4"),
            file_size=file_size,
            has_audio=has_audio,
            fps=fmt.get("fps"),
            vcodec=vcodec,
            acodec=acodec,
        )

        # Keep best format per resolution (prefer with audio, then largest size)
        existing = formats_map.get(height)
        if existing is None:
            formats_map[height] = fmt_obj
        else:
            # Prefer format with audio
            if fmt_obj.has_audio and not existing.has_audio:
                formats_map[height] = fmt_obj
            elif fmt_obj.has_audio == existing.has_audio:
                # Prefer larger file (better quality)
                if (fmt_obj.file_size or 0) > (existing.file_size or 0):
                    formats_map[height] = fmt_obj

    # Sort by height descending
    sorted_formats = sorted(formats_map.values(), key=lambda f: f.height, reverse=True)

    # If no file sizes, try to estimate from duration and typical bitrates
    for fmt in sorted_formats:
        if not fmt.file_size and duration > 0:
            fmt.file_size = _estimate_file_size(fmt.height, duration)

    # For TikTok, if formats extraction is poor, create a default
    if platform == "tiktok" and not sorted_formats:
        file_size = info.get("filesize") or info.get("filesize_approx")
        height = info.get("height", 1080)
        sorted_formats = [
            VideoFormat(
                format_id="best",
                quality_label=f"{height}p",
                height=height,
                ext="mp4",
                file_size=file_size or _estimate_file_size(height, duration),
                has_audio=True,
            )
        ]

    return VideoInfo(
        url=url,
        title=title,
        duration=duration,
        thumbnail=thumbnail,
        platform=platform,
        uploader=uploader,
        formats=sorted_formats,
    )


def _estimate_file_size(height: int, duration_sec: int) -> int:
    """Estimate file size based on resolution and duration."""
    # Approximate bitrates (video + audio) in bits/sec
    bitrate_map = {
        2160: 40_000_000,   # 4K: ~40 Mbps
        1440: 16_000_000,   # 2K: ~16 Mbps
        1080: 8_000_000,    # 1080p: ~8 Mbps
        720: 5_000_000,     # 720p: ~5 Mbps
        480: 2_500_000,     # 480p: ~2.5 Mbps
        360: 1_000_000,     # 360p: ~1 Mbps
        240: 500_000,       # 240p: ~0.5 Mbps
        144: 300_000,       # 144p: ~0.3 Mbps
    }
    # Find closest resolution
    closest = min(bitrate_map.keys(), key=lambda h: abs(h - height))
    bitrate = bitrate_map[closest]
    return int(bitrate * duration_sec / 8)


def get_telegram_compatible_formats(
    formats: List[VideoFormat],
    max_size: int,
) -> tuple[List[VideoFormat], List[VideoFormat]]:
    """
    Split formats into two lists:
    - fits_telegram: formats that fit in Telegram's file size limit
    - too_large: formats that exceed the limit

    Returns (fits_telegram, too_large)
    """
    fits = []
    too_large = []

    for fmt in formats:
        if fmt.file_size and fmt.file_size <= max_size:
            fits.append(fmt)
        elif fmt.file_size and fmt.file_size > max_size:
            too_large.append(fmt)
        else:
            # Unknown size — assume it fits if resolution <= 720p
            if fmt.height <= 720:
                fits.append(fmt)
            else:
                too_large.append(fmt)

    return fits, too_large
