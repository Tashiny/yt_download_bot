from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.models import (
    Base,
    DownloadHistory,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    language_code: Optional[str] = None,
) -> User:
    """Get existing user or create new one with trial subscription."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code or "ru",
            )
            session.add(user)
            await session.flush()

            # Create trial subscription
            trial_sub = Subscription(
                user_id=user.id,
                plan=SubscriptionPlan.TRIAL,
                status=SubscriptionStatus.ACTIVE,
                expires_at=datetime.utcnow() + timedelta(days=settings.trial_days),
            )
            session.add(trial_sub)
            await session.commit()
            await session.refresh(user)
        else:
            # Update user info
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            if language_code:
                user.language_code = language_code
            await session.commit()

        return user


async def get_user_subscription(telegram_id: int) -> Optional[Subscription]:
    """Get user's subscription."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription)
            .join(User)
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def update_subscription(
    telegram_id: int,
    plan: SubscriptionPlan,
    days: int = 30,
) -> Subscription:
    """Update or create subscription for user."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        sub = result.scalar_one_or_none()

        now = datetime.utcnow()
        expires = now + timedelta(days=days)

        if sub:
            sub.plan = plan
            sub.status = SubscriptionStatus.ACTIVE
            sub.started_at = now
            sub.expires_at = expires
            sub.downloads_today = 0
        else:
            sub = Subscription(
                user_id=user.id,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                started_at=now,
                expires_at=expires,
            )
            session.add(sub)

        await session.commit()
        await session.refresh(sub)
        return sub


async def increment_download_count(telegram_id: int) -> None:
    """Increment daily download counter."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription)
            .join(User)
            .where(User.telegram_id == telegram_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            if sub.last_download_date != today:
                sub.downloads_today = 1
                sub.last_download_date = today
            else:
                sub.downloads_today += 1
            await session.commit()


async def add_download_record(
    telegram_id: int,
    url: str,
    platform: str,
    title: str = "",
    quality: str = "",
    file_size: int = 0,
    via_web: bool = False,
) -> None:
    """Add download to history."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            record = DownloadHistory(
                user_id=user.id,
                url=url,
                platform=platform,
                title=title,
                quality=quality,
                file_size=file_size,
                via_web=via_web,
            )
            session.add(record)
            await session.commit()


async def get_user_stats(telegram_id: int) -> dict:
    """Get user download statistics."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return {"total_downloads": 0}

        result = await session.execute(
            select(DownloadHistory).where(DownloadHistory.user_id == user.id)
        )
        downloads = result.scalars().all()
        return {
            "total_downloads": len(downloads),
            "total_size": sum(d.file_size or 0 for d in downloads),
        }


async def get_all_users_count() -> int:
    """Get total users count."""
    async with async_session() as session:
        result = await session.execute(select(User))
        return len(result.scalars().all())


async def get_active_subs_count() -> int:
    """Get active subscriptions count."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at > datetime.utcnow(),
            )
        )
        return len(result.scalars().all())
