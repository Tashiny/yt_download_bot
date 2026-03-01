"""
Inline keyboards for the bot.
"""
from __future__ import annotations

from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import SubscriptionPlan
from services.video_info import VideoFormat


# ──────────── Main Menu ────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать видео", callback_data="help_download")],
        [InlineKeyboardButton(text="📋 Моя подписка", callback_data="my_subscription")],
        [InlineKeyboardButton(text="💳 Тарифы", callback_data="plans")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


# ──────────── Quality Selection ────────────

def quality_selection_kb(
    formats: List[VideoFormat],
    url: str,
    platform: str,
    fits_telegram: List[VideoFormat],
    too_large: List[VideoFormat],
    web_download_url: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Build quality selection keyboard.
    - Formats that fit Telegram: shown as direct download buttons
    - Formats too large: shown with 🌐 icon pointing to web
    """
    buttons: list[list[InlineKeyboardButton]] = []

    for fmt in fits_telegram:
        size_text = fmt.size_display
        label = f"📥 {fmt.quality_label} ({size_text})"
        callback = f"dl:{platform}:{fmt.format_id}:{fmt.height}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=callback)])

    if too_large:
        # Check if ANY format could be downloaded at lower quality
        if fits_telegram:
            buttons.append([InlineKeyboardButton(
                text="──── Слишком большие для Telegram ────",
                callback_data="noop",
            )])

        for fmt in too_large:
            size_text = fmt.size_display
            label = f"🌐 {fmt.quality_label} ({size_text}) — Веб-загрузка"
            if web_download_url:
                buttons.append([InlineKeyboardButton(
                    text=label,
                    url=web_download_url + f"?q={fmt.format_id}",
                )])
            else:
                callback = f"web:{platform}:{fmt.format_id}:{fmt.height}"
                buttons.append([InlineKeyboardButton(text=label, callback_data=callback)])

    if not fits_telegram and not too_large:
        buttons.append([InlineKeyboardButton(
            text="📥 Лучшее качество",
            callback_data=f"dl:{platform}:best:0",
        )])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_download")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def web_download_kb(web_url: str) -> InlineKeyboardMarkup:
    """Keyboard with link to web download page."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Скачать через веб", url=web_url)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])


# ──────────── Subscription Plans ────────────

def plans_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Basic — 99 Stars/мес",
            callback_data=f"buy:{SubscriptionPlan.BASIC.value}",
        )],
        [InlineKeyboardButton(
            text="💎 Premium — 249 Stars/мес",
            callback_data=f"buy:{SubscriptionPlan.PREMIUM.value}",
        )],
        [InlineKeyboardButton(
            text="🚀 Pro — 499 Stars/мес",
            callback_data=f"buy:{SubscriptionPlan.PRO.value}",
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])


def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Сменить план", callback_data="plans")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


# ──────────── Confirm Payment ────────────

def confirm_payment_kb(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Оплатить",
            callback_data=f"confirm_pay:{plan}",
        )],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="plans")],
    ])


# ──────────── Admin ────────────

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
    ])
