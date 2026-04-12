"""
サブスクリプションモデル

サブスクリプションサービスの情報を管理するORMモデル。
料金（日本円）、カテゴリ、更新日などを保持する。
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.models.user import User

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.subscription_category import SubscriptionCategory


class Subscription(Base):
    """サブスクリプションテーブルのORMモデル"""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    monthly_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    category: Mapped[SubscriptionCategory] = mapped_column(
        Enum(
            SubscriptionCategory,
            name="subscription_category",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # リレーション: このサブスクリプションを持つユーザー
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    # インデックス定義（DDLに対応）
    __table_args__ = (
        Index("idx_subscriptions_user_id", "user_id"),
        Index("idx_subscriptions_next_renewal_date", "next_renewal_date"),
        Index("idx_subscriptions_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, service_name='{self.service_name}', monthly_fee={self.monthly_fee})>"
