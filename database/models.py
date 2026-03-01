from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SubscriptionPlan(str, enum.Enum):
    TRIAL = "trial"
    BASIC = "basic"
    PREMIUM = "premium"
    PRO = "pro"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="ru")
    registered_at = Column(DateTime, default=func.now())
    is_banned = Column(Boolean, default=False)

    subscription = relationship("Subscription", back_populates="user", uselist=False)
    downloads = relationship("DownloadHistory", back_populates="user")

    @property
    def full_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or "Unknown"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.TRIAL)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    started_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    downloads_today = Column(Integer, default=0)
    last_download_date = Column(String(10), nullable=True)  # YYYY-MM-DD

    user = relationship("User", back_populates="subscription")

    @property
    def is_active(self) -> bool:
        return (
            self.status == SubscriptionStatus.ACTIVE
            and self.expires_at > datetime.utcnow()
        )

    @property
    def daily_limit(self) -> int:
        """Return daily download limit. -1 = unlimited."""
        from config import settings

        limits = {
            SubscriptionPlan.TRIAL: 3,
            SubscriptionPlan.BASIC: settings.plan_basic_downloads,
            SubscriptionPlan.PREMIUM: settings.plan_premium_downloads,
            SubscriptionPlan.PRO: settings.plan_pro_downloads,
        }
        return limits.get(self.plan, 0)

    @property
    def can_download(self) -> bool:
        if not self.is_active:
            return False
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self.last_download_date != today:
            return True
        limit = self.daily_limit
        if limit == -1:
            return True
        return self.downloads_today < limit


class DownloadHistory(Base):
    __tablename__ = "download_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    url = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False)  # youtube / tiktok
    title = Column(Text, nullable=True)
    quality = Column(String(20), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    downloaded_at = Column(DateTime, default=func.now())
    via_web = Column(Boolean, default=False)

    user = relationship("User", back_populates="downloads")
