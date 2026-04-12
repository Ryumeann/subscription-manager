"""
通知サービスの単体テスト（タスク7.2）

テスト対象:
- NotificationService.check_upcoming_renewals
- NotificationService.mark_renewal_processed
- NotificationService.calculate_next_renewal_date
- エッジケースとエラーケース
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.models.subscription_category import SubscriptionCategory
from backend.models.user import User
from backend.services.notification_service import NotificationService


def _make_subscription(
    db: Session,
    user_id: int,
    *,
    service_name: str,
    monthly_fee: Decimal = Decimal("980.00"),
    category: SubscriptionCategory = SubscriptionCategory.OTHER,
    start_date: date = date(2024, 1, 1),
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
# NotificationService.check_upcoming_renewals のテスト
# ==============================================================================


class TestCheckUpcomingRenewals:
    """更新予定チェック + 通知データ生成テスト"""

    def test_7日以内の更新予定を返す(self, db_session: Session, test_user: User):
        """今日から7日以内に更新日があるサブスクを RenewalNotification として返す"""
        service = NotificationService(db_session)
        today = date.today()

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            next_renewal_date=today + timedelta(days=3),
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 1
        assert result[0].subscription.id == sub.id
        assert result[0].days_until_renewal == 3
        assert result[0].is_overdue is False

    def test_今日が更新日のものを含む(self, db_session: Session, test_user: User):
        """今日が更新日のサブスクも含む（days_until_renewal=0）"""
        service = NotificationService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            next_renewal_date=today,
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 1
        assert result[0].days_until_renewal == 0
        assert result[0].is_overdue is False

    def test_期限切れを含む(self, db_session: Session, test_user: User):
        """更新日が過去のサブスクも含み is_overdue=True になる"""
        service = NotificationService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="期限切れサービス",
            next_renewal_date=today - timedelta(days=5),
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 1
        assert result[0].days_until_renewal == -5
        assert result[0].is_overdue is True

    def test_8日後の更新予定は含まれない(self, db_session: Session, test_user: User):
        """8日後の更新日は通知対象外"""
        service = NotificationService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="YouTube Premium",
            next_renewal_date=today + timedelta(days=8),
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 0

    def test_days_until_renewalの昇順で返す(
        self, db_session: Session, test_user: User
    ):
        """期限切れが先、更新が近い順（days_until_renewal 昇順）で返す"""
        service = NotificationService(db_session)
        today = date.today()

        # 期限切れ（-3日）、今日（0日）、3日後、7日後の順に並ぶべき
        _make_subscription(
            db_session,
            test_user.id,
            service_name="3日後",
            next_renewal_date=today + timedelta(days=3),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="期限切れ",
            next_renewal_date=today - timedelta(days=3),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="7日後",
            next_renewal_date=today + timedelta(days=7),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="今日",
            next_renewal_date=today,
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 4
        assert result[0].subscription.service_name == "期限切れ"
        assert result[1].subscription.service_name == "今日"
        assert result[2].subscription.service_name == "3日後"
        assert result[3].subscription.service_name == "7日後"

    def test_days引数を変更できる(self, db_session: Session, test_user: User):
        """days=3 を指定した場合、3日以内 + 期限切れのみ返す"""
        service = NotificationService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="2日後",
            next_renewal_date=today + timedelta(days=2),
        )
        _make_subscription(
            db_session,
            test_user.id,
            service_name="5日後",
            next_renewal_date=today + timedelta(days=5),
        )

        result = service.check_upcoming_renewals(test_user.id, days=3)

        assert len(result) == 1
        assert result[0].subscription.service_name == "2日後"

    def test_論理削除済みは含まれない(self, db_session: Session, test_user: User):
        """is_active=False のサブスクは通知対象外"""
        service = NotificationService(db_session)
        today = date.today()

        _make_subscription(
            db_session,
            test_user.id,
            service_name="解約済み",
            next_renewal_date=today + timedelta(days=1),
            is_active=False,
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 0

    def test_サブスクリプションが0件(self, db_session: Session, test_user: User):
        """サブスクリプションが存在しない場合は空リストを返す"""
        service = NotificationService(db_session)

        result = service.check_upcoming_renewals(test_user.id)

        assert result == []

    def test_RenewalNotificationに正しいフィールドが含まれる(
        self, db_session: Session, test_user: User
    ):
        """RenewalNotification の各フィールドが正しく設定される"""
        service = NotificationService(db_session)
        today = date.today()

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            next_renewal_date=today + timedelta(days=5),
        )

        result = service.check_upcoming_renewals(test_user.id)

        assert len(result) == 1
        notification = result[0]
        assert notification.subscription.id == sub.id
        assert notification.subscription.service_name == "Netflix"
        assert notification.subscription.monthly_fee == Decimal("1980.00")
        assert notification.days_until_renewal == 5
        assert notification.is_overdue is False


# ==============================================================================
# NotificationService.mark_renewal_processed のテスト
# ==============================================================================


class TestMarkRenewalProcessed:
    """期限切れサブスクリプションの自動更新テスト"""

    def test_次回更新日が1ヶ月進む(
        self, db_session: Session, test_user: User
    ):
        """mark_renewal_processed を呼ぶと next_renewal_date が1ヶ月進む"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            next_renewal_date=date(2024, 1, 15),
        )

        result = service.mark_renewal_processed(sub.id)

        assert result is True
        db_session.refresh(sub)
        assert sub.next_renewal_date == date(2024, 2, 15)

    def test_月末補正が正しく行われる(
        self, db_session: Session, test_user: User
    ):
        """1月31日 → 2月29日（2024年は閏年）に補正される"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            next_renewal_date=date(2024, 1, 31),
        )

        service.mark_renewal_processed(sub.id)

        db_session.refresh(sub)
        assert sub.next_renewal_date == date(2024, 2, 29)

    def test_年をまたぐ更新(
        self, db_session: Session, test_user: User
    ):
        """12月 → 翌年1月への更新日の進め"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="YouTube Premium",
            next_renewal_date=date(2024, 12, 10),
        )

        service.mark_renewal_processed(sub.id)

        db_session.refresh(sub)
        assert sub.next_renewal_date == date(2025, 1, 10)

    def test_存在しないIDはFalseを返す(
        self, db_session: Session, test_user: User
    ):
        """存在しないサブスクリプションIDを指定した場合は False を返す"""
        service = NotificationService(db_session)

        result = service.mark_renewal_processed(99999)

        assert result is False

    def test_論理削除済みはFalseを返す(
        self, db_session: Session, test_user: User
    ):
        """is_active=False のサブスクは更新対象外（False を返す）"""
        service = NotificationService(db_session)
        today = date.today()

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="解約済み",
            next_renewal_date=today - timedelta(days=5),
            is_active=False,
        )

        result = service.mark_renewal_processed(sub.id)

        assert result is False

    def test_DBに永続化される(
        self, db_session: Session, test_user: User
    ):
        """更新後の next_renewal_date が DB に保存される"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Apple Music",
            next_renewal_date=date(2024, 3, 20),
        )

        service.mark_renewal_processed(sub.id)

        # DBから直接取得して確認
        from_db = (
            db_session.query(Subscription)
            .filter(Subscription.id == sub.id)
            .first()
        )
        assert from_db is not None
        assert from_db.next_renewal_date == date(2024, 4, 20)


# ==============================================================================
# NotificationService.calculate_next_renewal_date のテスト
# ==============================================================================


class TestCalculateNextRenewalDate:
    """次回更新日計算テスト"""

    def test_通常の1ヶ月加算(self, db_session: Session, test_user: User):
        """通常の日付に1ヶ月を加算する"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Netflix",
            next_renewal_date=date(2024, 3, 15),
        )

        result = service.calculate_next_renewal_date(sub)

        assert result == date(2024, 4, 15)

    def test_月末補正_3月31日_4月30日(self, db_session: Session, test_user: User):
        """3月31日 → 4月30日（4月は30日まで）"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Spotify",
            next_renewal_date=date(2024, 3, 31),
        )

        result = service.calculate_next_renewal_date(sub)

        assert result == date(2024, 4, 30)

    def test_月末補正_1月31日_2月29日_閏年(self, db_session: Session, test_user: User):
        """1月31日 → 2月29日（2024年は閏年）"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="YouTube Premium",
            next_renewal_date=date(2024, 1, 31),
        )

        result = service.calculate_next_renewal_date(sub)

        assert result == date(2024, 2, 29)

    def test_月末補正_1月31日_2月28日_平年(self, db_session: Session, test_user: User):
        """1月31日 → 2月28日（2023年は平年）"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Amazon Prime",
            next_renewal_date=date(2023, 1, 31),
        )

        result = service.calculate_next_renewal_date(sub)

        assert result == date(2023, 2, 28)

    def test_年をまたぐ計算(self, db_session: Session, test_user: User):
        """12月 → 翌年1月への計算"""
        service = NotificationService(db_session)

        sub = _make_subscription(
            db_session,
            test_user.id,
            service_name="Nintendo Switch Online",
            next_renewal_date=date(2024, 12, 25),
        )

        result = service.calculate_next_renewal_date(sub)

        assert result == date(2025, 1, 25)
