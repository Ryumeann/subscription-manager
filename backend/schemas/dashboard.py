"""
ダッシュボード関連のPydanticスキーマ

ダッシュボードAPIのレスポンスデータ構造を定義。
design.md のスキーマ設計に準拠。
"""

from decimal import Decimal

from pydantic import BaseModel

from backend.schemas.subscription import MonthlySpending, SubscriptionResponse


class DashboardData(BaseModel):
    """ダッシュボードレスポンススキーマ"""

    total_monthly_expense: Decimal
    subscription_count: int
    category_breakdown: dict[str, Decimal]
    upcoming_renewals: list[SubscriptionResponse]
    monthly_trends: list[MonthlySpending]
