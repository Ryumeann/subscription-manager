"""
サブスクリプションサービス

サブスクリプションのCRUD操作、月間総支出計算、
カテゴリ別集計、次回更新日自動計算を担当する。

- CRUD: データベースへの作成・取得・更新・論理削除
- 月間合計: アクティブなサブスクリプションの月額料金合計
- カテゴリ集計: カテゴリ別の支出額をまとめた辞書
- 次回更新日: 未指定の場合は開始日の1ヶ月後を自動設定
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


def _add_one_month(d: date) -> date:
    """
    日付に1ヶ月加算する。

    月末日を超える場合（例: 1月31日 → 2月28日）は翌月末日に補正する。
    例:
        date(2024, 1, 31) → date(2024, 2, 29)  # 2024年は閏年
        date(2024, 3, 31) → date(2024, 4, 30)
    """
    month = d.month + 1
    year = d.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    # 翌月の最終日を超えないよう補正
    max_day = monthrange(year, month)[1]
    day = min(d.day, max_day)
    return date(year, month, day)


class SubscriptionService:
    """サブスクリプション管理サービスクラス"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- CRUD操作 ---

    def create_subscription(
        self, user_id: int, data: SubscriptionCreate
    ) -> Subscription:
        """
        サブスクリプションを新規作成する。

        next_renewal_date が未指定の場合は start_date の1ヶ月後を自動設定する。
        """
        next_renewal_date = data.next_renewal_date
        if next_renewal_date is None:
            next_renewal_date = _add_one_month(data.start_date)

        subscription = Subscription(
            user_id=user_id,
            service_name=data.service_name,
            monthly_fee=data.monthly_fee,
            category=data.category,
            start_date=data.start_date,
            next_renewal_date=next_renewal_date,
            memo=data.memo,
            is_active=True,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """
        ユーザーのアクティブなサブスクリプション一覧を取得する。

        is_active=False の論理削除済みレコードは含まない。
        """
        return (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.is_active == True,  # noqa: E712
            )
            .all()
        )

    def get_subscription_by_id(
        self, subscription_id: int, user_id: int
    ) -> Optional[Subscription]:
        """
        IDでサブスクリプションを取得する（所有者確認付き）。

        指定されたユーザーのアクティブなサブスクリプションのみ返す。
        見つからない場合は None を返す。
        """
        return (
            self.db.query(Subscription)
            .filter(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id,
                Subscription.is_active == True,  # noqa: E712
            )
            .first()
        )

    def update_subscription(
        self,
        subscription_id: int,
        user_id: int,
        data: SubscriptionUpdate,
    ) -> Optional[Subscription]:
        """
        サブスクリプションを更新する。

        送信されたフィールドのみ更新する（部分更新）。
        対象が存在しないまたは他ユーザーの場合は None を返す。
        """
        subscription = self.get_subscription_by_id(subscription_id, user_id)
        if subscription is None:
            return None

        # exclude_unset=True: リクエストで明示的に送信されたフィールドのみ更新
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(subscription, field, value)

        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def delete_subscription(self, subscription_id: int, user_id: int) -> bool:
        """
        サブスクリプションを論理削除する（is_active=False に設定）。

        物理削除ではなく論理削除を採用することで、履歴データを保持する。
        対象が存在しないまたは他ユーザーの場合は False を返す。
        """
        subscription = self.get_subscription_by_id(subscription_id, user_id)
        if subscription is None:
            return False

        subscription.is_active = False
        self.db.commit()
        return True

    # --- 集計・計算 ---

    def calculate_monthly_total(self, user_id: int) -> Decimal:
        """
        ユーザーの月間総支出額を計算する。

        アクティブなサブスクリプションの monthly_fee を合算する。
        サブスクリプションが0件の場合は Decimal("0") を返す。
        """
        subscriptions = self.get_user_subscriptions(user_id)
        return sum(
            (s.monthly_fee for s in subscriptions),
            Decimal("0"),
        )

    def get_category_breakdown(self, user_id: int) -> dict[str, Decimal]:
        """
        カテゴリ別の月額支出集計を返す。

        例: {"動画配信": Decimal("1980.00"), "音楽": Decimal("980.00")}

        サブスクリプションが0件の場合は空辞書を返す。
        カテゴリ値は SubscriptionCategory の value（日本語文字列）を使用する。
        """
        subscriptions = self.get_user_subscriptions(user_id)
        breakdown: dict[str, Decimal] = {}
        for s in subscriptions:
            category_value = s.category.value
            if category_value not in breakdown:
                breakdown[category_value] = Decimal("0")
            breakdown[category_value] += s.monthly_fee
        return breakdown
