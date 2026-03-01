"""
Middleware to check subscription status before processing messages.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database.db import get_or_create_user, get_user_subscription
from keyboards.inline import plans_kb


class SubscriptionMiddleware(BaseMiddleware):
    """Check that user has active subscription for download-related actions."""

    # Callbacks that don't require subscription
    FREE_CALLBACKS = {
        "main_menu", "plans", "help", "help_download",
        "my_subscription", "my_stats", "noop",
    }

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Determine user
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if not user:
            return await handler(event, data)

        # Ensure user exists in DB
        db_user = await get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )
        data["db_user"] = db_user

        # Load subscription
        sub = await get_user_subscription(user.id)
        data["subscription"] = sub

        # Check if this is a download action
        is_download_action = False

        if isinstance(event, Message) and event.text:
            from services.video_info import is_valid_url
            if is_valid_url(event.text):
                is_download_action = True

        if isinstance(event, CallbackQuery) and event.data:
            cb = event.data
            if cb.startswith("dl:") or cb.startswith("web:"):
                is_download_action = True
            # Allow free callbacks
            if any(cb.startswith(free) for free in self.FREE_CALLBACKS):
                is_download_action = False
            if cb.startswith("buy:") or cb.startswith("confirm_pay:"):
                is_download_action = False
            if cb.startswith("admin"):
                is_download_action = False

        if is_download_action:
            if not sub or not sub.is_active:
                text = (
                    "⚠️ <b>Подписка не активна</b>\n\n"
                    "Для загрузки видео необходима активная подписка.\n"
                    "Оформите один из тарифных планов:"
                )
                if isinstance(event, CallbackQuery):
                    await event.message.edit_text(text, reply_markup=plans_kb(), parse_mode="HTML")
                    await event.answer()
                elif isinstance(event, Message):
                    await event.answer(text, reply_markup=plans_kb(), parse_mode="HTML")
                return

            if not sub.can_download:
                text = (
                    "⚠️ <b>Лимит загрузок исчерпан</b>\n\n"
                    f"Вы достигли дневного лимита загрузок для вашего плана.\n"
                    "Обновите подписку для увеличения лимита или подождите до завтра."
                )
                if isinstance(event, CallbackQuery):
                    await event.message.edit_text(text, reply_markup=plans_kb(), parse_mode="HTML")
                    await event.answer()
                elif isinstance(event, Message):
                    await event.answer(text, reply_markup=plans_kb(), parse_mode="HTML")
                return

        return await handler(event, data)
