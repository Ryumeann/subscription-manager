"""
ダッシュボードサービスの単体テスト（タスク6.2）

テスト対象:
- DashboardService.get_dashboard_data
- DashboardService.get_category_breakdown
- DashboardService.get_spending_trends
- DashboardService.get_upcoming_renewals
- エッジケースとエラーケース
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.models.subscription_category import SubscriptionCategory
from backend.models.user import User
from backend.services.dashboard_service import DashboardService


def _make_subscription(
    db: Session,
    user_id: int,
    *,
    service_name: str,
    monthly_fee: Decimal,
    category: SubscriptionCategory = SubscriptionCategory.OTHER,
    start_date: date,
    next_renewal_date: date,
    is_active: bool = True,
) -> Subscription:
    """テスト用サブスクリプション作成ヘルパー"""
    sub = Subscription(
        user_id=user_id,
        service_name=service_name,
        monthly_fee=monthly_fee,
        category=category,
        start_date=start_date,
        next_renewal_date=next_renewal_date,
        is_active=is_active,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ==============================================================================
# DashboardService.get_upcoming_renewals のテスト
# ==============================================================================


class TestGetUpcomingRenewals:
    """更新予定取得テスト"""

    def test_7日以内の更新予定を取得(self, db_session: Session, test_user: User):
        """今日から7日以内に更新日があるサブスクリプションを返す"""
        service = DashboardService(db_session)
        today = date.today()

        # 3日後に更新
        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=3),
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 1
        assert result[0].id == sub.id

    def test_今日が更新日のものを含む(self, db_session: Session, test_user: User):
        """今日が更新日のサブスクリプションも含む"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today,
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 1

    def test_8日後の更新予定は含まれない(self, db_session: Session, test_user: User):
        """8日後の更新日は取得対象外"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="YouTube Premium",
            monthly_fee=Decimal("1180.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=8),
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 0

    def test_過去の更新日は含まれない(self, db_session: Session, test_user: User):
        """過去の更新日は取得対象外"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Amazon Prime",
            monthly_fee=Decimal("600.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today - timedelta(days=1),
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 0

    def test_更新日の昇順で返す(self, db_session: Session, test_user: User):
        """複数件のとき next_renewal_date の昇順で返す"""
        service = DashboardService(db_session)
        today = date.today()

        sub_later = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=5),
        )
        sub_sooner = _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=1),
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 2
        assert result[0].id == sub_sooner.id
        assert result[1].id == sub_later.id

    def test_論理削除済みは含まれない(self, db_session: Session, test_user: User):
        """is_active=False のサブスクリプションは除外する"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Hulu",
            monthly_fee=Decimal("1026.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=2),
            is_active=False,
        )

        result = service.get_upcoming_renewals(test_user.id)

        assert len(result) == 0

    def test_サブスクリプションが0件(self, db_session: Session, test_user: User):
        """サブスクリプションが存在しない場合は空リストを返す"""
        service = DashboardService(db_session)

        result = service.get_upcoming_renewals(test_user.id)

        assert result == []

    def test_days引数を変更できる(self, db_session: Session, test_user: User):
        """days=3 を指定した場合、3日以内の更新予定のみ返す"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=2),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=5),
        )

        result = service.get_upcoming_renewals(test_user.id, days=3)

        assert len(result) == 1
        assert result[0].service_name == "Netflix"


# ==============================================================================
# DashboardService.get_spending_trends のテスト
# ==============================================================================


class TestGetSpendingTrends:
    """月別支出推移テスト"""

    def test_12件のMonthlySpendingを返す(self, db_session: Session, test_user: User):
        """デフォルトで12ヶ月分のデータを返す"""
        service = DashboardService(db_session)

        result = service.get_spending_trends(test_user.id)

        assert len(result) == 12

    def test_古い月から昇順で返す(self, db_session: Session, test_user: User):
        """過去11ヶ月前から今月の昇順で返す"""
        service = DashboardService(db_session)
        today = date.today()

        result = service.get_spending_trends(test_user.id)

        # 最初が11ヶ月前、最後が今月
        assert result[-1].year == today.year
        assert result[-1].month == today.month

        # 月が昇順になっている（年をまたぐ場合は年も考慮）
        for i in range(1, len(result)):
            prev = result[i - 1]
            curr = result[i]
            assert (prev.year, prev.month) < (curr.year, curr.month)

    def test_サブスクリプションが0件は全月0円(
        self, db_session: Session, test_user: User
    ):
        """サブスクリプションが存在しない場合、全月の合計が0"""
        service = DashboardService(db_session)

        result = service.get_spending_trends(test_user.id)

        for monthly in result:
            assert monthly.total_amount == Decimal("0")

    def test_start_date以前の月は0円(self, db_session: Session, test_user: User):
        """サブスクリプションの start_date 以前の月は合計が0になる"""
        service = DashboardService(db_session)
        today = date.today()

        # 今月1日から開始するサブスクリプション
        _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            start_date=date(today.year, today.month, 1),
            next_renewal_date=date(today.year, today.month, 1) + timedelta(days=30),
        )

        result = service.get_spending_trends(test_user.id)

        # 今月のみ1980円、それ以前は0円
        assert result[-1].total_amount == Decimal("1980.00")
        for monthly in result[:-1]:
            assert monthly.total_amount == Decimal("0")

    def test_months引数を変更できる(self, db_session: Session, test_user: User):
        """months=3 を指定した場合、3ヶ月分のデータを返す"""
        service = DashboardService(db_session)

        result = service.get_spending_trends(test_user.id, months=3)

        assert len(result) == 3

    def test_論理削除済みは集計に含まれない(
        self, db_session: Session, test_user: User
    ):
        """is_active=False のサブスクリプションは支出推移に含まれない"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="解約済みサービス",
            monthly_fee=Decimal("999.00"),
            start_date=date(2020, 1, 1),
            next_renewal_date=date(2020, 2, 1),
            is_active=False,
        )

        result = service.get_spending_trends(test_user.id)

        # is_active=False なので全月0円
        for monthly in result:
            assert monthly.total_amount == Decimal("0")


# ==============================================================================
# DashboardService.get_category_breakdown のテスト
# ==============================================================================


class TestGetCategoryBreakdown:
    """カテゴリ別集計テスト（DashboardService 経由）"""

    def test_カテゴリ別に集計される(self, db_session: Session, test_user: User):
        """SubscriptionService に委譲してカテゴリ別集計を返す"""
        service = DashboardService(db_session)

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            category=SubscriptionCategory.MUSIC,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )

        result = service.get_category_breakdown(test_user.id)

        assert result["動画配信"] == Decimal("1980.00")
        assert result["音楽"] == Decimal("980.00")

    def test_サブスクリプションが0件は空辞書(
        self, db_session: Session, test_user: User
    ):
        """サブスクリプションが存在しない場合は空辞書を返す"""
        service = DashboardService(db_session)

        result = service.get_category_breakdown(test_user.id)

        assert result == {}


# ==============================================================================
# DashboardService.get_dashboard_data のテスト
# ==============================================================================


class TestGetDashboardData:
    """ダッシュボード全データ取得テスト"""

    def test_全フィールドが含まれる(self, db_session: Session, test_user: User):
        """DashboardData の全フィールドが正しく含まれる"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=3),
        )

        data = service.get_dashboard_data(test_user.id)

        assert data.total_monthly_expense == Decimal("1980.00")
        assert data.subscription_count == 1
        assert data.category_breakdown["動画配信"] == Decimal("1980.00")
        assert len(data.upcoming_renewals) == 1
        assert len(data.monthly_trends) == 12

    def test_サブスクリプションが0件(self, db_session: Session, test_user: User):
        """サブスクリプションが存在しない場合のデフォルト値"""
        service = DashboardService(db_session)

        data = service.get_dashboard_data(test_user.id)

        assert data.total_monthly_expense == Decimal("0")
        assert data.subscription_count == 0
        assert data.category_breakdown == {}
        assert data.upcoming_renewals == []
        assert len(data.monthly_trends) == 12

    def test_upcoming_renewalsはSubscriptionResponseのリスト(
        self, db_session: Session, test_user: User
    ):
        """upcoming_renewals は SubscriptionResponse に変換されている"""
        from backend.schemas.subscription import SubscriptionResponse

        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=1),
        )

        data = service.get_dashboard_data(test_user.id)

        assert len(data.upcoming_renewals) == 1
        assert isinstance(data.upcoming_renewals[0], SubscriptionResponse)

    def test_7日以降の更新はupcoming_renewalsに含まれない(
        self, db_session: Session, test_user: User
    ):
        """8日後の更新予定はダッシュボードの upcoming_renewals に含まれない"""
        service = DashboardService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="YouTube Premium",
            monthly_fee=Decimal("1180.00"),
            start_date=date(2024, 1, 1),
            next_renewal_date=today + timedelta(days=8),
        )

        data = service.get_dashboard_data(test_user.id)

        assert len(data.upcoming_renewals) == 0
