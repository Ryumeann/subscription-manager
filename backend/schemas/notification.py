"""
通知関連のPydanticスキーマ

更新予定通知のレスポンスデータ構造を定義。
"""

from pydantic import BaseModel

from backend.schemas.subscription import SubscriptionResponse


class RenewalNotification(BaseModel):
    """更新予定通知スキーマ"""

    subscription: SubscriptionResponse
    days_until_renewal: int
    """更新日までの残り日数。負の値は期限切れを示す（例: -3 は3日前に期限切れ）"""
    is_overdue: bool
    """next_renewal_date が過去の場合 True"""
