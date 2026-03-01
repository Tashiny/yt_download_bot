"""
Video download handlers.
Core logic: URL detection → video info → quality selection → download → send.
Smart file-size handling for Telegram's 2 GB limit.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramEntityTooLarge
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    Message,
)
from itsdangerous import URLSafeTimedSerializer

from config import settings
from database.db import add_download_record, increment_download_count
from keyboards.inline import (
    back_to_menu_kb,
    quality_selection_kb,
    web_download_kb,
)
from services.downloader import cleanup_file, download_video, get_file_size
from services.subscription import get_max_quality_height
from services.video_info import (
    VideoFormat,
    detect_platform,
    extract_url,
    get_telegram_compatible_formats,
    get_video_info,
    is_valid_url,
)

logger = logging.getLogger(__name__)
router = Router(name="download")

# Token serializer for secure web download links
serializer = URLSafeTimedSerializer(settings.secret_key)

# Store pending downloads: {user_id: VideoInfo}
_pending_downloads: dict[int, dict] = {}


def _generate_web_token(user_id: int, url: str, format_id: str) -> str:
    """Generate secure token for web download."""
    return serializer.dumps({
        "user_id": user_id,
        "url": url,
        "format_id": format_id,
    })


def _build_web_url(user_id: int, url: str, format_id: str, platform: str) -> str:
    """Build full web download URL."""
    token = _generate_web_token(user_id, url, format_id)
    return f"{settings.web_base_url}/download/{token}"


# ──────────── URL Message Handler ────────────

@router.message(F.text)
async def handle_url(message: Message, subscription=None, **kwargs) -> None:
    """Handle incoming URL messages."""
    text = message.text.strip()

    if not is_valid_url(text):
        return  # Not a URL, ignore

    url = extract_url(text)
    if not url:
        await message.answer("❌ Не удалось распознать ссылку. Проверьте и попробуйте ещё раз.")
        return

    platform = detect_platform(url)
    if not platform:
        await message.answer(
            "❌ Поддерживаются только ссылки с <b>YouTube</b> и <b>TikTok</b>.",
            parse_mode="HTML",
        )
        return

    # Check subscription quality limit
    max_height = 4320  # default
    if subscription:
        max_height = get_max_quality_height(subscription.plan)

    # Show loading message
    platform_emoji = "🎬" if platform == "youtube" else "🎵"
    loading_msg = await message.answer(
        f"{platform_emoji} Получаю информацию о видео...\n"
        "⏳ Это может занять несколько секунд.",
        parse_mode="HTML",
    )

    try:
        video_info = await get_video_info(url)
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        await loading_msg.edit_text(
            "❌ <b>Ошибка получения информации</b>\n\n"
            "Не удалось получить информацию о видео.\n"
            "Проверьте ссылку и попробуйте ещё раз.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )
        return

    # Filter formats by subscription quality limit
    available_formats = [f for f in video_info.formats if f.height <= max_height]

    if not available_formats:
        # If all formats are above limit, take the lowest available
        if video_info.formats:
            available_formats = [min(video_info.formats, key=lambda f: f.height)]
        else:
            available_formats = []

    # Split into Telegram-compatible and too-large
    fits, too_large = get_telegram_compatible_formats(
        available_formats, settings.max_telegram_file_size
    )

    # Store pending download info
    _pending_downloads[message.from_user.id] = {
        "url": url,
        "platform": platform,
        "title": video_info.title,
        "formats": {f.format_id: f for f in available_formats},
    }

    # Determine if we need web download links
    # If ALL formats are too large → only web option
    all_too_large = len(fits) == 0 and len(too_large) > 0

    # Build quality selection text
    title_short = video_info.title[:60] + ("..." if len(video_info.title) > 60 else "")
    text = (
        f"{platform_emoji} <b>{title_short}</b>\n\n"
        f"👤 {video_info.uploader}\n"
        f"⏱ {video_info.duration_display}\n\n"
    )

    if all_too_large:
        text += (
            "⚠️ <b>Все доступные качества превышают лимит Telegram (2 ГБ)</b>\n\n"
            "Скачайте видео через веб-интерфейс:"
        )
        # Generate web URL for best available format
        best = too_large[0] if too_large else available_formats[0]
        web_url = _build_web_url(
            message.from_user.id, url, best.format_id, platform
        )

        # Also show lower qualities that STILL don't fit
        await loading_msg.edit_text(
            text,
            reply_markup=web_download_kb(web_url),
            parse_mode="HTML",
        )
        return

    text += "🎯 <b>Выберите качество загрузки:</b>"

    # Build web URLs for too_large formats
    web_base = None
    if too_large:
        web_base = f"{settings.web_base_url}/download"

    # Build keyboard with quality buttons
    # For web-only formats, create individual web links
    web_url_for_large = None
    if too_large:
        first_large = too_large[0]
        web_url_for_large = _build_web_url(
            message.from_user.id, url, first_large.format_id, platform
        )

    kb = quality_selection_kb(
        formats=available_formats,
        url=url,
        platform=platform,
        fits_telegram=fits,
        too_large=too_large,
        web_download_url=web_url_for_large,
    )

    await loading_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ──────────── Direct Download Callback ────────────

@router.callback_query(F.data.startswith("dl:"))
async def cb_download(callback: CallbackQuery, subscription=None, **kwargs) -> None:
    """
    Handle direct download. Callback data format: dl:platform:format_id:height
    """
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка формата")
        return

    _, platform, format_id, height_str = parts[0], parts[1], parts[2], parts[3]

    pending = _pending_downloads.get(callback.from_user.id)
    if not pending:
        await callback.answer("⚠️ Сессия истекла. Отправьте ссылку заново.", show_alert=True)
        return

    url = pending["url"]
    title = pending["title"]

    # Edit message to show download progress
    await callback.message.edit_text(
        f"📥 <b>Загрузка видео...</b>\n\n"
        f"🎬 {title[:50]}...\n"
        f"📊 Качество: {height_str}p\n\n"
        "⏳ Пожалуйста, подождите. Это может занять некоторое время.",
        parse_mode="HTML",
    )
    await callback.answer()

    try:
        # Download video
        file_path = await download_video(
            url=url,
            format_id=format_id,
            platform=platform,
        )

        file_size = get_file_size(file_path)

        # Double-check file size
        if file_size > settings.max_telegram_file_size:
            # File turned out larger than expected → offer web download
            web_url = _build_web_url(
                callback.from_user.id, url, format_id, platform
            )
            await callback.message.edit_text(
                "⚠️ <b>Файл оказался больше ожидаемого</b>\n\n"
                f"📦 Размер: {file_size / (1024**3):.2f} ГБ\n"
                "Telegram не позволяет отправить файлы более 2 ГБ.\n\n"
                "Скачайте через веб-интерфейс:",
                reply_markup=web_download_kb(web_url),
                parse_mode="HTML",
            )
            # Keep file for web download (will be cleaned up later)
            return

        # Send video file
        await callback.message.edit_text(
            "📤 <b>Отправка видео...</b>\n\n"
            "⏳ Файл загружается в Telegram...",
            parse_mode="HTML",
        )

        video_file = FSInputFile(file_path, filename=f"{title[:50]}.mp4")
        caption_text = (
            f"🎬 <b>{title[:100]}</b>\n"
            f"📊 Качество: {height_str}p\n"
            f"📦 Размер: {file_size / (1024**2):.1f} МБ"
        )

        try:
            # Try sending as video first (better preview in chat)
            await callback.message.answer_video(
                video=video_file,
                caption=caption_text,
                parse_mode="HTML",
            )
        except TelegramEntityTooLarge:
            # File too large for Telegram upload → offer web download
            web_url = _build_web_url(
                callback.from_user.id, url, format_id, platform
            )
            await callback.message.edit_text(
                "⚠️ <b>Файл слишком большой для Telegram</b>\n\n"
                f"📦 Размер: {file_size / (1024**2):.1f} МБ\n"
                "Скачайте через веб-интерфейс:",
                reply_markup=web_download_kb(web_url),
                parse_mode="HTML",
            )
            return
        except Exception:
            # Fallback: try as document
            video_file = FSInputFile(file_path, filename=f"{title[:50]}.mp4")
            await callback.message.answer_document(
                document=video_file,
                caption=caption_text,
                parse_mode="HTML",
            )

        # Update download counter
        await increment_download_count(callback.from_user.id)
        await add_download_record(
            telegram_id=callback.from_user.id,
            url=url,
            platform=platform,
            title=title,
            quality=f"{height_str}p",
            file_size=file_size,
        )

        # Clean up
        await callback.message.edit_text(
            "✅ <b>Видео успешно загружено!</b>\n\n"
            "Отправьте ещё одну ссылку для загрузки.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )

        cleanup_file(file_path)

    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки</b>\n\n"
            f"Произошла ошибка при загрузке видео.\n"
            "Попробуйте другое качество или повторите позже.",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML",
        )

    # Clean up pending
    _pending_downloads.pop(callback.from_user.id, None)


# ──────────── Web Download Callback ────────────

@router.callback_query(F.data.startswith("web:"))
async def cb_web_download(callback: CallbackQuery, **kwargs) -> None:
    """Generate web download link for large files."""
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка")
        return

    _, platform, format_id, height_str = parts[0], parts[1], parts[2], parts[3]

    pending = _pending_downloads.get(callback.from_user.id)
    if not pending:
        await callback.answer("⚠️ Сессия истекла. Отправьте ссылку заново.", show_alert=True)
        return

    url = pending["url"]
    web_url = _build_web_url(callback.from_user.id, url, format_id, platform)

    await callback.message.edit_text(
        f"🌐 <b>Веб-загрузка</b>\n\n"
        f"Качество: {height_str}p\n"
        "Нажмите кнопку ниже для скачивания через браузер:",
        reply_markup=web_download_kb(web_url),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────── Cancel ────────────

@router.callback_query(F.data == "cancel_download")
async def cb_cancel(callback: CallbackQuery, **kwargs) -> None:
    _pending_downloads.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        "❌ Загрузка отменена.",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
