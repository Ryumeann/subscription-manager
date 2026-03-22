"""
通知サービス

サブスクリプションの更新予定チェックと、
期限切れサブスクリプションの次回更新日自動計算を担当する。

- check_upcoming_renewals: 7日以内の更新予定 + 期限切れを通知データとして返す
- mark_renewal_processed: 期限切れの次回更新日を1ヶ月進める（自動更新処理）
- calculate_next_renewal_date: 次回更新日を計算する（_add_one_month に委譲）

要件との対応:
- 要件5.1: 更新日が7日以内のサブスクを注意が必要としてマーク
- 要件5.2: 更新日の昇順でソート（期限切れが先、更新が近い順）
- 要件5.3: 更新日が過ぎたとき次回更新日を自動計算
- 要件5.4: 期限切れを is_overdue フラグで示す
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.schemas.notification import RenewalNotification
from backend.schemas.subscription import SubscriptionResponse
from backend.services.subscription_service import _add_one_month


class NotificationService:
    """通知サービスクラス"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_upcoming_renewals(
        self, user_id: int, days: int = 7
    ) -> list[RenewalNotification]:
        """
        更新予定と期限切れのサブスクリプションを通知データとして返す。

        以下の2種類を対象とする:
        - 今日から days 日以内に更新日があるサブスクリプション（要件5.1）
        - 更新日が過ぎているサブスクリプション（要件5.4）

        days_until_renewal の昇順（期限切れが先、更新が近い順）で返す。

        引数:
            user_id: 対象ユーザーID
            days: 通知対象とする残り日数（デフォルト: 7日）
        """
        today = date.today()

        # アクティブなサブスクリプションを一括取得
        subscriptions = (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.is_active == True,  # noqa: E712
            )
            .all()
        )

        notifications: list[RenewalNotification] = []
        for sub in subscriptions:
            days_until = (sub.next_renewal_date - today).days
            is_overdue = days_until < 0

            # 期限切れ（days_until < 0）または days 日以内が対象
            if days_until <= days:
                notifications.append(
                    RenewalNotification(
                        subscription=SubscriptionResponse.model_validate(sub),
                        days_until_renewal=days_until,
                        is_overdue=is_overdue,
                    )
                )

        # days_until_renewal の昇順（期限切れが先、更新が近い順）
        notifications.sort(key=lambda n: n.days_until_renewal)
        return notifications

    def mark_renewal_processed(self, subscription_id: int) -> bool:
        """
        サブスクリプションの次回更新日を1ヶ月進める。

        更新日が過ぎたサブスクリプションに対して呼び出し、
        次の更新サイクルの日付を自動計算してDBを更新する（要件5.3）。

        引数:
            subscription_id: 対象サブスクリプションID

        戻り値:
            更新に成功した場合 True、対象が存在しない場合 False
        """
        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.id == subscription_id,
                Subscription.is_active == True,  # noqa: E712
            )
            .first()
        )

        if subscription is None:
            return False

        subscription.next_renewal_date = self.calculate_next_renewal_date(subscription)
        self.db.commit()
        return True

    def calculate_next_renewal_date(self, subscription: Subscription) -> date:
        """
        サブスクリプションの次回更新日を計算する。

        現在の next_renewal_date に1ヶ月を加算する。
        月末日をまたぐ場合は翌月末日に補正する。

        例:
            next_renewal_date=2024-01-31 → 2024-02-29（閏年）
            next_renewal_date=2024-03-31 → 2024-04-30
        """
        return _add_one_month(subscription.next_renewal_date)
