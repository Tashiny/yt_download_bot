"""
Start and basic navigation handlers.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message

from database.db import get_or_create_user, get_user_stats
from keyboards.inline import back_to_menu_kb, main_menu_kb
from services.subscription import get_subscription_text

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )

    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        "🎬 Я бот для скачивания видео с <b>YouTube</b> и <b>TikTok</b>.\n\n"
        "📱 <b>Что я умею:</b>\n"
        "• Скачивать видео с YouTube в любом качестве\n"
        "• Скачивать видео из TikTok без водяных знаков\n"
        "• Выбирать качество видео перед загрузкой\n"
        "• Скачивать большие файлы через веб-интерфейс\n\n"
        "🎁 У вас есть <b>3 дня пробного периода</b>!\n\n"
        "Просто отправьте мне ссылку на видео 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(
        "📋 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    text = (
        "📋 <b>Главное меню</b>\n\n"
        "Отправьте ссылку на видео или выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    text = (
        "❓ <b>Помощь</b>\n\n"
        "🔹 <b>Как скачать видео:</b>\n"
        "Просто отправьте мне ссылку на видео с YouTube или TikTok.\n\n"
        "🔹 <b>Поддерживаемые платформы:</b>\n"
        "• YouTube (видео, shorts)\n"
        "• TikTok (без водяных знаков)\n\n"
        "🔹 <b>Выбор качества:</b>\n"
        "После отправки ссылки бот покажет доступные качества.\n"
        "Выберите нужное — и видео будет загружено!\n\n"
        "🔹 <b>Большие файлы:</b>\n"
        "Если видео больше 2 ГБ, бот предложит скачать его\n"
        "через веб-интерфейс или понизить качество.\n\n"
        "🔹 <b>Подписка:</b>\n"
        "Бот предоставляет 3 дня бесплатного пробного периода.\n"
        "После этого необходимо оформить подписку.\n\n"
        "📩 Поддержка: @your_support_username"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "help_download")
async def cb_help_download(callback: CallbackQuery) -> None:
    text = (
        "📥 <b>Как скачать видео</b>\n\n"
        "1️⃣ Скопируйте ссылку на видео\n"
        "2️⃣ Отправьте её мне в чат\n"
        "3️⃣ Выберите качество из предложенных\n"
        "4️⃣ Дождитесь загрузки\n\n"
        "💡 <b>Примеры ссылок:</b>\n"
        "• https://youtube.com/watch?v=...\n"
        "• https://youtu.be/...\n"
        "• https://youtube.com/shorts/...\n"
        "• https://tiktok.com/@user/video/...\n\n"
        "Отправьте ссылку прямо сейчас! 👇"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)

    total = stats.get("total_downloads", 0)
    total_size = stats.get("total_size", 0)

    if total_size > 1_073_741_824:
        size_text = f"{total_size / 1_073_741_824:.1f} ГБ"
    elif total_size > 1_048_576:
        size_text = f"{total_size / 1_048_576:.0f} МБ"
    else:
        size_text = f"{total_size / 1024:.0f} КБ"

    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"📥 Всего загрузок: <b>{total}</b>\n"
        f"💾 Объём загруженного: <b>{size_text}</b>\n"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
