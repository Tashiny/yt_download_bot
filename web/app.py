"""
FastAPI web application for downloading large video files.
Provides a beautiful web page with secure download links.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import settings
from services.downloader import cleanup_file, download_video
from services.video_info import get_video_info

logger = logging.getLogger(__name__)

app = FastAPI(title="Video Downloader", docs_url=None, redoc_url=None)

# Templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Static files
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Token serializer (same as in bot)
serializer = URLSafeTimedSerializer(settings.secret_key)

# Track active web downloads
_web_downloads: dict[str, Path] = {}


@app.get("/health")
async def health():
    """Healthcheck endpoint for Railway/Docker."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/download/{token}", response_class=HTMLResponse)
async def download_page(request: Request, token: str):
    """
    Show download page with video info.
    Token contains user_id, url, format_id.
    """
    try:
        data = serializer.loads(token, max_age=3600)  # 1 hour expiry
    except SignatureExpired:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_title": "Ссылка истекла",
            "error_message": "Ссылка для скачивания устарела. Отправьте ссылку на видео заново в бот.",
        })
    except BadSignature:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_title": "Недействительная ссылка",
            "error_message": "Ссылка для скачивания недействительна.",
        })

    url = data.get("url")
    format_id = data.get("format_id")
    user_id = data.get("user_id")

    try:
        video_info = await get_video_info(url)
    except Exception as e:
        logger.error(f"Web download info error: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_title": "Ошибка",
            "error_message": "Не удалось получить информацию о видео.",
        })

    # Find the requested format
    fmt = None
    for f in video_info.formats:
        if f.format_id == format_id:
            fmt = f
            break

    return templates.TemplateResponse("download.html", {
        "request": request,
        "video": video_info,
        "format": fmt,
        "token": token,
        "format_id": format_id,
    })


@app.post("/download/{token}/start")
async def start_download(token: str):
    """
    Start the actual download process.
    Returns JSON with download status.
    """
    try:
        data = serializer.loads(token, max_age=3600)
    except (SignatureExpired, BadSignature):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    url = data.get("url")
    format_id = data.get("format_id")
    user_id = data.get("user_id")

    try:
        file_path = await download_video(
            url=url,
            format_id=format_id,
            platform="youtube",  # yt-dlp handles both
        )
        _web_downloads[token] = file_path
        return {"status": "ready", "filename": file_path.name}
    except Exception as e:
        logger.error(f"Web download error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{token}/file")
async def serve_file(token: str):
    """Serve the downloaded file."""
    try:
        data = serializer.loads(token, max_age=7200)  # 2 hours for download
    except (SignatureExpired, BadSignature):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    file_path = _web_downloads.get(token)

    if not file_path or not file_path.exists():
        # Try to download again
        url = data.get("url")
        format_id = data.get("format_id")
        try:
            file_path = await download_video(url=url, format_id=format_id, platform="youtube")
            _web_downloads[token] = file_path
        except Exception:
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="video/mp4",
    )


@app.on_event("shutdown")
async def shutdown():
    """Clean up downloaded files."""
    for token, path in _web_downloads.items():
        cleanup_file(path)
    _web_downloads.clear()
