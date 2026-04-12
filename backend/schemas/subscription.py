"""
サブスクリプション関連のPydanticスキーマ

リクエスト・レスポンスのデータバリデーションとシリアライゼーションを定義。
design.md のスキーマ設計に準拠。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.subscription_category import SubscriptionCategory


class SubscriptionCreate(BaseModel):
    """サブスクリプション新規作成リクエストスキーマ"""

    service_name: str = Field(
        ..., min_length=1, max_length=100, description="サービス名"
    )
    monthly_fee: Decimal = Field(
        ..., gt=0, max_digits=10, decimal_places=2, description="月額料金（円）"
    )
    category: SubscriptionCategory = Field(..., description="カテゴリ")
    start_date: date = Field(..., description="契約開始日")
    next_renewal_date: Optional[date] = Field(
        None, description="次回更新日（未指定の場合は開始日の1ヶ月後）"
    )
    memo: Optional[str] = Field(
        None, max_length=500, description="メモ"
    )


class SubscriptionUpdate(BaseModel):
    """サブスクリプション更新リクエストスキーマ"""

    service_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="サービス名"
    )
    monthly_fee: Optional[Decimal] = Field(
        None, gt=0, max_digits=10, decimal_places=2, description="月額料金（円）"
    )
    category: Optional[SubscriptionCategory] = Field(
        None, description="カテゴリ"
    )
    start_date: Optional[date] = Field(None, description="契約開始日")
    next_renewal_date: Optional[date] = Field(None, description="次回更新日")
    memo: Optional[str] = Field(
        None, max_length=500, description="メモ"
    )


class SubscriptionResponse(BaseModel):
    """サブスクリプションレスポンススキーマ"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    service_name: str
    monthly_fee: Decimal
    category: SubscriptionCategory
    start_date: date
    next_renewal_date: date
    memo: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MonthlySpending(BaseModel):
    """月別支出データスキーマ"""

    year: int
    month: int
    total_amount: Decimal
