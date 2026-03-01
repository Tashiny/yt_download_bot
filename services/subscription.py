"""
Subscription management service.
"""
from __future__ import annotations

from datetime import datetime

from config import settings
from database.db import get_user_subscription, update_subscription
from database.models import SubscriptionPlan, SubscriptionStatus


PLAN_INFO = {
    SubscriptionPlan.TRIAL: {
        "name": "🆓 Пробный период",
        "price": 0,
        "days": settings.trial_days,
        "downloads_per_day": 3,
        "max_quality": "1080p",
        "features": [
            f"✅ {settings.trial_days} дня бесплатно",
            "✅ 3 загрузки в день",
            "✅ Качество до 1080p",
            "✅ YouTube и TikTok",
        ],
    },
    SubscriptionPlan.BASIC: {
        "name": "⭐ Basic",
        "price": settings.plan_basic_price,
        "days": 30,
        "downloads_per_day": settings.plan_basic_downloads,
        "max_quality": "1080p",
        "features": [
            f"✅ {settings.plan_basic_downloads} загрузок в день",
            "✅ Качество до 1080p",
            "✅ YouTube и TikTok",
            "✅ Без водяных знаков",
            f"💰 {settings.plan_basic_price} Stars / месяц",
        ],
    },
    SubscriptionPlan.PREMIUM: {
        "name": "💎 Premium",
        "price": settings.plan_premium_price,
        "days": 30,
        "downloads_per_day": settings.plan_premium_downloads,
        "max_quality": "4K",
        "features": [
            f"✅ {settings.plan_premium_downloads} загрузок в день",
            "✅ Качество до 4K",
            "✅ YouTube и TikTok",
            "✅ Без водяных знаков",
            "✅ Приоритетная загрузка",
            f"💰 {settings.plan_premium_price} Stars / месяц",
        ],
    },
    SubscriptionPlan.PRO: {
        "name": "🚀 Pro",
        "price": settings.plan_pro_price,
        "days": 30,
        "downloads_per_day": -1,
        "max_quality": "4K+",
        "features": [
            "✅ Безлимитные загрузки",
            "✅ Максимальное качество",
            "✅ YouTube и TikTok",
            "✅ Без водяных знаков",
            "✅ Приоритетная загрузка",
            "✅ Веб-загрузка больших файлов",
            f"💰 {settings.plan_pro_price} Stars / месяц",
        ],
    },
}


def get_plan_info(plan: SubscriptionPlan) -> dict:
    return PLAN_INFO.get(plan, PLAN_INFO[SubscriptionPlan.TRIAL])


async def get_subscription_text(telegram_id: int) -> str:
    """Generate subscription status text for user."""
    sub = await get_user_subscription(telegram_id)

    if not sub:
        return "❌ У вас нет активной подписки. Оформите подписку для использования бота."

    plan_info = get_plan_info(sub.plan)
    status_emoji = "✅" if sub.is_active else "❌"
    status_text = "Активна" if sub.is_active else "Истекла"

    today = datetime.utcnow().strftime("%Y-%m-%d")
    downloads_today = sub.downloads_today if sub.last_download_date == today else 0
    limit = sub.daily_limit
    limit_text = f"{downloads_today}/{limit}" if limit != -1 else f"{downloads_today}/∞"

    expires_text = sub.expires_at.strftime("%d.%m.%Y %H:%M") if sub.expires_at else "—"

    text = (
        f"📋 <b>Ваша подписка</b>\n\n"
        f"📦 План: {plan_info['name']}\n"
        f"{status_emoji} Статус: {status_text}\n"
        f"📅 Действует до: {expires_text}\n"
        f"📥 Загрузок сегодня: {limit_text}\n"
        f"🎬 Макс. качество: {plan_info['max_quality']}\n"
    )

    if not sub.is_active:
        text += "\n⚠️ <b>Подписка истекла!</b> Оформите новую для продолжения."

    return text


def get_plans_text() -> str:
    """Generate text with all available plans."""
    text = "💳 <b>Тарифные планы</b>\n\n"
    for plan in [SubscriptionPlan.BASIC, SubscriptionPlan.PREMIUM, SubscriptionPlan.PRO]:
        info = PLAN_INFO[plan]
        text += f"<b>{info['name']}</b>\n"
        for feature in info["features"]:
            text += f"  {feature}\n"
        text += "\n"
    return text


def get_max_quality_height(plan: SubscriptionPlan) -> int:
    """Return max video height allowed for plan."""
    quality_map = {
        SubscriptionPlan.TRIAL: 1080,
        SubscriptionPlan.BASIC: 1080,
        SubscriptionPlan.PREMIUM: 2160,
        SubscriptionPlan.PRO: 4320,
    }
    return quality_map.get(plan, 720)
