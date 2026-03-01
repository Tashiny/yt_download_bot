"""
Main entry point for the Telegram bot.
Runs both the bot (aiogram) and the web server (FastAPI/uvicorn) concurrently.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database.db import init_db
from handlers import admin, download, start, subscription
from middlewares.subscription import SubscriptionMiddleware
from web.app import app as web_app

# ──────────── Logging ────────────

log_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
try:
    log_handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))
except OSError:
    pass  # read-only FS in some containers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)


# ──────────── Web Server ────────────

async def run_web_server() -> None:
    """Run FastAPI web server for large file downloads."""
    # Railway/Render inject PORT env var — use it if available
    port = int(os.environ.get("PORT", settings.web_port))
    logger.info(f"Web server starting on 0.0.0.0:{port}")
    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


# ──────────── Bot Polling ────────────

async def run_bot() -> None:
    """Initialize bot and start polling. Retries on failure."""
    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set! Bot will not start.")
        return

    try:
        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        dp = Dispatcher()

        # Register middleware
        dp.message.middleware(SubscriptionMiddleware())
        dp.callback_query.middleware(SubscriptionMiddleware())

        # Register routers (order matters — admin and subscription before download)
        dp.include_router(start.router)
        dp.include_router(admin.router)
        dp.include_router(subscription.router)
        dp.include_router(download.router)  # last — catch-all URL handler

        logger.info("Bot polling started")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot polling failed: {e}", exc_info=True)


# ──────────── Main ────────────

async def main() -> None:
    logger.info("=" * 50)
    logger.info("Video Downloader Bot starting...")
    logger.info("=" * 50)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    logger.info(f"Web base URL: {settings.web_base_url}")

    # Start web server FIRST (for healthcheck), then bot
    await asyncio.gather(
        run_web_server(),
        run_bot(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
