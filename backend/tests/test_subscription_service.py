"""
サブスクリプションサービスの単体テスト（タスク5.2）

テスト対象:
- SubscriptionService のCRUD操作
- 月間総支出計算
- カテゴリ別集計
- 次回更新日自動計算
- エッジケースとエラーケース
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.models.subscription_category import SubscriptionCategory
from backend.models.user import User
from backend.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from backend.services.subscription_service import SubscriptionService, _add_one_month


# ==============================================================================
# _add_one_month のテスト
# ==============================================================================


class TestAddOneMonth:
    """次回更新日自動計算の補助関数テスト"""

    def test_通常の月加算(self):
        """通常の日付に1ヶ月を加算する"""
        assert _add_one_month(date(2024, 1, 15)) == date(2024, 2, 15)

    def test_年をまたぐ月加算(self):
        """12月から1月への月加算（年をまたぐ）"""
        assert _add_one_month(date(2024, 12, 10)) == date(2025, 1, 10)

    def test_月末日の補正_31日_4月(self):
        """3月31日 → 4月30日（4月は30日まで）"""
        assert _add_one_month(date(2024, 3, 31)) == date(2024, 4, 30)

    def test_月末日の補正_31日_2月_閏年(self):
        """1月31日 → 2月29日（閏年2024年）"""
        assert _add_one_month(date(2024, 1, 31)) == date(2024, 2, 29)

    def test_月末日の補正_31日_2月_平年(self):
        """1月31日 → 2月28日（平年2023年）"""
        assert _add_one_month(date(2023, 1, 31)) == date(2023, 2, 28)

    def test_月末日の補正_30日_2月(self):
        """1月30日 → 2月28日（平年2023年）"""
        assert _add_one_month(date(2023, 1, 30)) == date(2023, 2, 28)

    def test_年末_12月31日(self):
        """12月31日 → 1月31日（翌年）"""
        assert _add_one_month(date(2024, 12, 31)) == date(2025, 1, 31)


# ==============================================================================
# SubscriptionService.create_subscription のテスト
# ==============================================================================


class TestCreateSubscription:
    """サブスクリプション作成テスト"""

    def test_正常な作成(self, db_session: Session, test_user: User):
        """全フィールド指定でサブスクリプションを作成できる"""
        service = SubscriptionService(db_session)
        data = SubscriptionCreate(
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            memo="動画配信サービス",
        )

        subscription = service.create_subscription(test_user.id, data)

        assert subscription.id is not None
        assert subscription.user_id == test_user.id
        assert subscription.service_name == "Netflix"
        assert subscription.monthly_fee == Decimal("1980.00")
        assert subscription.category == SubscriptionCategory.VIDEO_STREAMING
        assert subscription.start_date == date(2024, 1, 1)
        assert subscription.next_renewal_date == date(2024, 2, 1)
        assert subscription.memo == "動画配信サービス"
        assert subscription.is_active is True

    def test_next_renewal_date未指定で自動計算される(
        self, db_session: Session, test_user: User
    ):
        """next_renewal_date を省略した場合、start_date の1ヶ月後が設定される"""
        service = SubscriptionService(db_session)
        data = SubscriptionCreate(
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            category=SubscriptionCategory.MUSIC,
            start_date=date(2024, 3, 15),
        )

        subscription = service.create_subscription(test_user.id, data)

        assert subscription.next_renewal_date == date(2024, 4, 15)

    def test_next_renewal_date未指定_月末補正(
        self, db_session: Session, test_user: User
    ):
        """start_date が月末の場合、翌月末日に補正される"""
        service = SubscriptionService(db_session)
        data = SubscriptionCreate(
            service_name="YouTube Premium",
            monthly_fee=Decimal("1180.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 31),
        )

        subscription = service.create_subscription(test_user.id, data)

        # 2024年2月は閏年なので29日
        assert subscription.next_renewal_date == date(2024, 2, 29)

    def test_memo未指定(self, db_session: Session, test_user: User):
        """メモなしでサブスクリプションを作成できる"""
        service = SubscriptionService(db_session)
        data = SubscriptionCreate(
            service_name="Apple Music",
            monthly_fee=Decimal("1080.00"),
            category=SubscriptionCategory.MUSIC,
            start_date=date(2024, 1, 1),
        )

        subscription = service.create_subscription(test_user.id, data)

        assert subscription.memo is None

    def test_データベースに永続化される(self, db_session: Session, test_user: User):
        """作成したサブスクリプションがDBに保存されることを確認"""
        service = SubscriptionService(db_session)
        data = SubscriptionCreate(
            service_name="Amazon Prime",
            monthly_fee=Decimal("600.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
        )

        subscription = service.create_subscription(test_user.id, data)

        # DBから直接取得して確認
        from_db = (
            db_session.query(Subscription)
            .filter(Subscription.id == subscription.id)
            .first()
        )
        assert from_db is not None
        assert from_db.service_name == "Amazon Prime"


# ==============================================================================
# SubscriptionService.get_user_subscriptions のテスト
# ==============================================================================


class TestGetUserSubscriptions:
    """サブスクリプション一覧取得テスト"""

    def test_アクティブなサブスクリプションのみ取得(
        self, db_session: Session, test_user: User
    ):
        """is_active=True のサブスクリプションのみ返す"""
        service = SubscriptionService(db_session)

        # アクティブなサブスク
        active = Subscription(
            user_id=test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=True,
        )
        # 論理削除済みサブスク
        inactive = Subscription(
            user_id=test_user.id,
            service_name="Hulu",
            monthly_fee=Decimal("1026.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2023, 1, 1),
            next_renewal_date=date(2023, 2, 1),
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        result = service.get_user_subscriptions(test_user.id)

        assert len(result) == 1
        assert result[0].service_name == "Netflix"

    def test_複数のサブスクリプション取得(self, db_session: Session, test_user: User):
        """複数のサブスクリプションをすべて取得できる"""
        service = SubscriptionService(db_session)

        for name, category in [
            ("Netflix", SubscriptionCategory.VIDEO_STREAMING),
            ("Spotify", SubscriptionCategory.MUSIC),
            ("Nintendo Switch Online", SubscriptionCategory.GAMING),
        ]:
            sub = Subscription(
                user_id=test_user.id,
                service_name=name,
                monthly_fee=Decimal("980.00"),
                category=category,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            )
            db_session.add(sub)
        db_session.commit()

        result = service.get_user_subscriptions(test_user.id)

        assert len(result) == 3

    def test_サブスクリプションが0件(self, db_session: Session, test_user: User):
        """サブスクリプションが存在しない場合は空リストを返す"""
        service = SubscriptionService(db_session)
        result = service.get_user_subscriptions(test_user.id)
        assert result == []

    def test_他ユーザーのサブスクリプションは取得されない(
        self, db_session: Session, test_user: User
    ):
        """別ユーザーのサブスクリプションは返さない"""
        from backend.services.auth_service import AuthService

        service = SubscriptionService(db_session)

        # 別ユーザー作成
        other_user = User(
            username="otheruser",
            hashed_password=AuthService.hash_password("password"),
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # 別ユーザーのサブスク
        other_sub = Subscription(
            user_id=other_user.id,
            service_name="Disney+",
            monthly_fee=Decimal("990.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=True,
        )
        db_session.add(other_sub)
        db_session.commit()

        result = service.get_user_subscriptions(test_user.id)

        assert len(result) == 0


# ==============================================================================
# SubscriptionService.update_subscription のテスト
# ==============================================================================


class TestUpdateSubscription:
    """サブスクリプション更新テスト"""

    def test_正常な部分更新(
        self, db_session: Session, test_user: User, test_subscription: Subscription
    ):
        """指定したフィールドのみ更新される"""
        service = SubscriptionService(db_session)
        data = SubscriptionUpdate(
            service_name="Netflix（更新済み）",
            monthly_fee=Decimal("2200.00"),
        )

        updated = service.update_subscription(
            test_subscription.id, test_user.id, data
        )

        assert updated is not None
        assert updated.service_name == "Netflix（更新済み）"
        assert updated.monthly_fee == Decimal("2200.00")
        # 変更していないフィールドは元のまま
        assert updated.category == test_subscription.category

    def test_カテゴリ更新(
        self, db_session: Session, test_user: User, test_subscription: Subscription
    ):
        """カテゴリを更新できる"""
        service = SubscriptionService(db_session)
        data = SubscriptionUpdate(category=SubscriptionCategory.OTHER)

        updated = service.update_subscription(
            test_subscription.id, test_user.id, data
        )

        assert updated is not None
        assert updated.category == SubscriptionCategory.OTHER

    def test_存在しないIDはNoneを返す(self, db_session: Session, test_user: User):
        """存在しないサブスクリプションIDを指定した場合は None を返す"""
        service = SubscriptionService(db_session)
        data = SubscriptionUpdate(service_name="更新テスト")

        result = service.update_subscription(99999, test_user.id, data)

        assert result is None

    def test_他ユーザーのサブスクリプションは更新できない(
        self, db_session: Session, test_subscription: Subscription
    ):
        """別ユーザーのサブスクリプションは更新できない（None を返す）"""
        from backend.services.auth_service import AuthService

        service = SubscriptionService(db_session)

        # 別ユーザー作成
        other_user = User(
            username="anotheruser",
            hashed_password=AuthService.hash_password("password"),
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        data = SubscriptionUpdate(service_name="不正な更新")
        result = service.update_subscription(
            test_subscription.id, other_user.id, data
        )

        assert result is None

    def test_next_renewal_date更新(
        self, db_session: Session, test_user: User, test_subscription: Subscription
    ):
        """次回更新日を更新できる"""
        service = SubscriptionService(db_session)
        new_date = date(2025, 6, 1)
        data = SubscriptionUpdate(next_renewal_date=new_date)

        updated = service.update_subscription(
            test_subscription.id, test_user.id, data
        )

        assert updated is not None
        assert updated.next_renewal_date == new_date


# ==============================================================================
# SubscriptionService.delete_subscription のテスト
# ==============================================================================


class TestDeleteSubscription:
    """サブスクリプション削除テスト"""

    def test_正常な論理削除(
        self, db_session: Session, test_user: User, test_subscription: Subscription
    ):
        """論理削除で is_active=False になる"""
        service = SubscriptionService(db_session)

        result = service.delete_subscription(test_subscription.id, test_user.id)

        assert result is True

        # DBから直接確認
        from_db = (
            db_session.query(Subscription)
            .filter(Subscription.id == test_subscription.id)
            .first()
        )
        assert from_db is not None
        assert from_db.is_active is False

    def test_削除後は一覧に含まれない(
        self, db_session: Session, test_user: User, test_subscription: Subscription
    ):
        """削除後、get_user_subscriptions に含まれない"""
        service = SubscriptionService(db_session)

        service.delete_subscription(test_subscription.id, test_user.id)
        result = service.get_user_subscriptions(test_user.id)

        assert len(result) == 0

    def test_存在しないIDはFalseを返す(self, db_session: Session, test_user: User):
        """存在しないIDを指定した場合は False を返す"""
        service = SubscriptionService(db_session)

        result = service.delete_subscription(99999, test_user.id)

        assert result is False

    def test_他ユーザーのサブスクリプションは削除できない(
        self, db_session: Session, test_subscription: Subscription
    ):
        """別ユーザーのサブスクリプションは削除できない（False を返す）"""
        from backend.services.auth_service import AuthService

        service = SubscriptionService(db_session)

        other_user = User(
            username="deleteuser",
            hashed_password=AuthService.hash_password("password"),
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        result = service.delete_subscription(test_subscription.id, other_user.id)

        assert result is False

        # 元のサブスクリプションはアクティブのまま
        from_db = (
            db_session.query(Subscription)
            .filter(Subscription.id == test_subscription.id)
            .first()
        )
        assert from_db is not None
        assert from_db.is_active is True


# ==============================================================================
# SubscriptionService.calculate_monthly_total のテスト
# ==============================================================================


class TestCalculateMonthlyTotal:
    """月間総支出計算テスト"""

    def test_複数サブスクリプションの合計(
        self, db_session: Session, test_user: User
    ):
        """複数のサブスクリプションの月額料金を合算する"""
        service = SubscriptionService(db_session)

        for name, fee in [
            ("Netflix", Decimal("1980.00")),
            ("Spotify", Decimal("980.00")),
            ("Nintendo Switch Online", Decimal("306.00")),
        ]:
            sub = Subscription(
                user_id=test_user.id,
                service_name=name,
                monthly_fee=fee,
                category=SubscriptionCategory.OTHER,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            )
            db_session.add(sub)
        db_session.commit()

        total = service.calculate_monthly_total(test_user.id)

        assert total == Decimal("3266.00")

    def test_サブスクリプションが0件の場合は0(
        self, db_session: Session, test_user: User
    ):
        """サブスクリプションが存在しない場合は Decimal("0") を返す"""
        service = SubscriptionService(db_session)

        total = service.calculate_monthly_total(test_user.id)

        assert total == Decimal("0")

    def test_論理削除済みは合計に含まれない(
        self, db_session: Session, test_user: User
    ):
        """is_active=False のサブスクリプションは合計に含まない"""
        service = SubscriptionService(db_session)

        active = Subscription(
            user_id=test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=True,
        )
        inactive = Subscription(
            user_id=test_user.id,
            service_name="Hulu",
            monthly_fee=Decimal("1026.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2023, 1, 1),
            next_renewal_date=date(2023, 2, 1),
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        total = service.calculate_monthly_total(test_user.id)

        assert total == Decimal("1980.00")

    def test_1件のサブスクリプション(self, db_session: Session, test_user: User):
        """1件のサブスクリプションの月額料金がそのまま返る"""
        service = SubscriptionService(db_session)

        sub = Subscription(
            user_id=test_user.id,
            service_name="YouTube Premium",
            monthly_fee=Decimal("1180.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=True,
        )
        db_session.add(sub)
        db_session.commit()

        total = service.calculate_monthly_total(test_user.id)

        assert total == Decimal("1180.00")


# ==============================================================================
# SubscriptionService.get_category_breakdown のテスト
# ==============================================================================


class TestGetCategoryBreakdown:
    """カテゴリ別集計テスト"""

    def test_複数カテゴリの集計(self, db_session: Session, test_user: User):
        """カテゴリ別に月額料金を集計する"""
        service = SubscriptionService(db_session)

        subs = [
            Subscription(
                user_id=test_user.id,
                service_name="Netflix",
                monthly_fee=Decimal("1980.00"),
                category=SubscriptionCategory.VIDEO_STREAMING,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Amazon Prime Video",
                monthly_fee=Decimal("600.00"),
                category=SubscriptionCategory.VIDEO_STREAMING,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Spotify",
                monthly_fee=Decimal("980.00"),
                category=SubscriptionCategory.MUSIC,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Nintendo Switch Online",
                monthly_fee=Decimal("306.00"),
                category=SubscriptionCategory.GAMING,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            ),
        ]
        db_session.add_all(subs)
        db_session.commit()

        breakdown = service.get_category_breakdown(test_user.id)

        assert breakdown["動画配信"] == Decimal("2580.00")  # 1980 + 600
        assert breakdown["音楽"] == Decimal("980.00")
        assert breakdown["ゲーム"] == Decimal("306.00")
        assert "その他" not in breakdown  # データなし

    def test_サブスクリプションが0件は空辞書(
        self, db_session: Session, test_user: User
    ):
        """サブスクリプションが存在しない場合は空辞書を返す"""
        service = SubscriptionService(db_session)

        breakdown = service.get_category_breakdown(test_user.id)

        assert breakdown == {}

    def test_論理削除済みは集計に含まれない(
        self, db_session: Session, test_user: User
    ):
        """is_active=False のサブスクリプションはカテゴリ集計に含まない"""
        service = SubscriptionService(db_session)

        active = Subscription(
            user_id=test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=True,
        )
        inactive = Subscription(
            user_id=test_user.id,
            service_name="Hulu",
            monthly_fee=Decimal("1026.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2023, 1, 1),
            next_renewal_date=date(2023, 2, 1),
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        breakdown = service.get_category_breakdown(test_user.id)

        assert breakdown["動画配信"] == Decimal("1980.00")

    def test_同一カテゴリのサブスクが合算される(
        self, db_session: Session, test_user: User
    ):
        """同じカテゴリの複数サブスクリプションは合算される"""
        service = SubscriptionService(db_session)

        for name, fee in [
            ("Spotify", Decimal("980.00")),
            ("Apple Music", Decimal("1080.00")),
            ("YouTube Music", Decimal("980.00")),
        ]:
            sub = Subscription(
                user_id=test_user.id,
                service_name=name,
                monthly_fee=fee,
                category=SubscriptionCategory.MUSIC,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
                is_active=True,
            )
            db_session.add(sub)
        db_session.commit()

        breakdown = service.get_category_breakdown(test_user.id)

        assert breakdown["音楽"] == Decimal("3040.00")  # 980 + 1080 + 980
