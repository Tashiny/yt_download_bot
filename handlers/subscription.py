"""
Subscription and payment handlers.
Uses Telegram Stars for payments.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import settings
from database.db import update_subscription
from database.models import SubscriptionPlan
from keyboards.inline import (
    back_to_menu_kb,
    confirm_payment_kb,
    plans_kb,
    subscription_kb,
)
from services.subscription import (
    PLAN_INFO,
    get_plans_text,
    get_subscription_text,
)

logger = logging.getLogger(__name__)
router = Router(name="subscription")


# ──────────── View Subscription ────────────

@router.callback_query(F.data == "my_subscription")
async def cb_my_subscription(callback: CallbackQuery, **kwargs) -> None:
    text = await get_subscription_text(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=subscription_kb(), parse_mode="HTML")
    await callback.answer()


# ──────────── View Plans ────────────

@router.callback_query(F.data == "plans")
async def cb_plans(callback: CallbackQuery, **kwargs) -> None:
    text = get_plans_text()
    await callback.message.edit_text(text, reply_markup=plans_kb(), parse_mode="HTML")
    await callback.answer()


# ──────────── Buy Plan ────────────

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_plan(callback: CallbackQuery, **kwargs) -> None:
    plan_name = callback.data.split(":")[1]

    try:
        plan = SubscriptionPlan(plan_name)
    except ValueError:
        await callback.answer("❌ Неизвестный план")
        return

    info = PLAN_INFO.get(plan)
    if not info:
        await callback.answer("❌ План не найден")
        return

    text = (
        f"💳 <b>Оформление подписки</b>\n\n"
        f"📦 План: <b>{info['name']}</b>\n"
        f"💰 Стоимость: <b>{info['price']} Stars</b>\n"
        f"📅 Период: <b>{info['days']} дней</b>\n\n"
        f"<b>Возможности:</b>\n"
    )
    for feature in info["features"]:
        text += f"{feature}\n"

    text += "\nПодтвердите оплату:"

    await callback.message.edit_text(
        text,
        reply_markup=confirm_payment_kb(plan_name),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────── Confirm Payment (Telegram Stars) ────────────

@router.callback_query(F.data.startswith("confirm_pay:"))
async def cb_confirm_payment(callback: CallbackQuery, **kwargs) -> None:
    plan_name = callback.data.split(":")[1]

    try:
        plan = SubscriptionPlan(plan_name)
    except ValueError:
        await callback.answer("❌ Ошибка")
        return

    info = PLAN_INFO.get(plan)
    if not info:
        await callback.answer("❌ Ошибка")
        return

    price = info["price"]

    # Send invoice with Telegram Stars
    await callback.message.answer_invoice(
        title=f"Подписка {info['name']}",
        description=(
            f"Подписка на {info['days']} дней.\n"
            f"Загрузок в день: {'безлимит' if info['downloads_per_day'] == -1 else info['downloads_per_day']}\n"
            f"Макс. качество: {info['max_quality']}"
        ),
        payload=f"sub_{plan_name}_{callback.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label=info["name"], amount=price)],
    )
    await callback.answer()


# ──────────── Pre-Checkout ────────────

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Approve the payment."""
    await query.answer(ok=True)


# ──────────── Successful Payment ────────────

@router.message(F.successful_payment)
async def successful_payment(message: Message, **kwargs) -> None:
    """Handle successful payment."""
    payment = message.successful_payment
    payload = payment.invoice_payload  # e.g. "sub_basic_123456"

    parts = payload.split("_")
    if len(parts) < 3:
        logger.error(f"Invalid payment payload: {payload}")
        return

    plan_name = parts[1]

    try:
        plan = SubscriptionPlan(plan_name)
    except ValueError:
        logger.error(f"Invalid plan in payment: {plan_name}")
        return

    info = PLAN_INFO.get(plan)
    days = info["days"] if info else 30

    # Activate subscription
    sub = await update_subscription(
        telegram_id=message.from_user.id,
        plan=plan,
        days=days,
    )

    await message.answer(
        f"🎉 <b>Подписка оформлена!</b>\n\n"
        f"📦 План: <b>{info['name']}</b>\n"
        f"📅 Действует до: <b>{sub.expires_at.strftime('%d.%m.%Y')}</b>\n\n"
        "Отправьте ссылку на видео для загрузки! 🎬",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )

    logger.info(
        f"Payment successful: user={message.from_user.id}, "
        f"plan={plan_name}, stars={payment.total_amount}"
    )
