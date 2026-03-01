"""
Admin panel handlers.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import settings
from database.db import get_active_subs_count, get_all_users_count
from keyboards.inline import admin_kb, back_to_menu_kb

logger = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🔧 <b>Панель администратора</b>",
        reply_markup=admin_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, **kwargs) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    total_users = await get_all_users_count()
    active_subs = await get_active_subs_count()

    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n"
    )

    await callback.message.edit_text(text, reply_markup=admin_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, **kwargs) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки.\n"
        "Отправьте /cancel для отмены.",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
