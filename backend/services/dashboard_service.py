"""
ダッシュボードサービス

ダッシュボード表示に必要なデータ集計を担当するサービスクラス。
月間支出、カテゴリ別内訳、支出推移（12ヶ月）、更新予定を提供する。

- get_dashboard_data: ダッシュボード全データをまとめて返す
- get_category_breakdown: カテゴリ別支出の辞書（SubscriptionService に委譲）
- get_spending_trends: 過去N月の月別支出推移（古い月から昇順）
- get_upcoming_renewals: 指定日数以内に更新日が来るサブスクリプション一覧
"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.schemas.dashboard import DashboardData
from backend.schemas.subscription import MonthlySpending, SubscriptionResponse
from backend.services.subscription_service import SubscriptionService


class DashboardService:
    """ダッシュボードデータ集計サービスクラス"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._subscription_service = SubscriptionService(db)

    def get_dashboard_data(self, user_id: int) -> DashboardData:
        """
        ダッシュボード表示に必要な全データをまとめて返す。

        月間総支出、アクティブ件数、カテゴリ別内訳、
        更新予定（7日以内）、12ヶ月支出推移を含む。
        """
        subscriptions = self._subscription_service.get_user_subscriptions(user_id)
        upcoming_orm = self.get_upcoming_renewals(user_id)

        return DashboardData(
            total_monthly_expense=self._subscription_service.calculate_monthly_total(
                user_id
            ),
            subscription_count=len(subscriptions),
            category_breakdown=self._subscription_service.get_category_breakdown(
                user_id
            ),
            upcoming_renewals=[
                SubscriptionResponse.model_validate(s) for s in upcoming_orm
            ],
            monthly_trends=self.get_spending_trends(user_id),
        )

    def get_category_breakdown(self, user_id: int) -> dict[str, Decimal]:
        """
        カテゴリ別の月額支出集計を返す。

        SubscriptionService.get_category_breakdown に委譲する。
        例: {"動画配信": Decimal("1980.00"), "音楽": Decimal("980.00")}
        """
        return self._subscription_service.get_category_breakdown(user_id)

    def get_spending_trends(
        self, user_id: int, months: int = 12
    ) -> list[MonthlySpending]:
        """
        過去N月の月別支出推移を返す（古い月から昇順）。

        各月について、現在アクティブなサブスクリプションのうち
        start_date がその月の末日以前のものの月額合計を集計する。

        例: months=3、今月が2024年3月の場合
            → [2024年1月, 2024年2月, 2024年3月] の順で返す

        注意: is_active=True のサブスクリプションのみ対象。
        過去に解約済み（is_active=False）のデータは含まれない。
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

        result: list[MonthlySpending] = []
        for i in range(months - 1, -1, -1):
            # i月前の年月を計算（今月が i=0）
            month = today.month - i
            year = today.year
            # 月が0以下になる場合は年をさかのぼる
            while month <= 0:
                month += 12
                year -= 1

            # その月の末日
            last_day = monthrange(year, month)[1]
            month_end = date(year, month, last_day)

            # start_date がその月の末日以前のサブスクリプションを集計
            total = sum(
                (s.monthly_fee for s in subscriptions if s.start_date <= month_end),
                Decimal("0"),
            )
            result.append(MonthlySpending(year=year, month=month, total_amount=total))

        return result

    def get_upcoming_renewals(
        self, user_id: int, days: int = 7
    ) -> list[Subscription]:
        """
        指定日数以内に更新日が来るアクティブなサブスクリプション一覧を返す。

        今日から days 日後までの next_renewal_date を持つサブスクリプションを
        更新日の昇順で返す。今日が更新日のものも含む。
        """
        today = date.today()
        threshold = today + timedelta(days=days)

        return (
            self.db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.is_active == True,  # noqa: E712
                Subscription.next_renewal_date >= today,
                Subscription.next_renewal_date <= threshold,
            )
            .order_by(Subscription.next_renewal_date)
            .all()
        )
