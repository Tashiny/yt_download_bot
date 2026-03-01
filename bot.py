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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ──────────── Bot Setup ────────────

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


# ──────────── Web Server ────────────

async def run_web_server() -> None:
    """Run FastAPI web server for large file downloads."""
    # Railway/Render inject PORT env var — use it if available
    port = int(os.environ.get("PORT", settings.web_port))
    config = uvicorn.Config(
        web_app,
        host=settings.web_host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


# ──────────── Main ────────────

async def main() -> None:
    logger.info("=" * 50)
    logger.info("Video Downloader Bot starting...")
    logger.info("=" * 50)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start bot and web server concurrently
    logger.info(f"Web server: {settings.web_base_url}")
    logger.info("Bot polling started")

    await asyncio.gather(
        dp.start_polling(bot),
        run_web_server(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
