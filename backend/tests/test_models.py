"""
データモデルの単体テスト

SQLAlchemyモデル（User、Subscription）のCRUD操作と
データ永続化を検証する。
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from backend.models.subscription import Subscription
from backend.models.subscription_category import SubscriptionCategory
from backend.models.user import User
from backend.services.auth_service import AuthService


class TestUserModel:
    """Userモデルのテストクラス"""

    def test_create_user(self, db_session: Session):
        """ユーザー作成テスト"""
        user = User(
            username="newuser",
            email="newuser@example.com",
            hashed_password=AuthService.hash_password("password123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_unique_username(self, db_session: Session, test_user: User):
        """ユーザー名の一意性制約テスト"""
        duplicate_user = User(
            username=test_user.username,  # 重複するユーザー名
            email="different@example.com",
            hashed_password=AuthService.hash_password("password123"),
        )
        db_session.add(duplicate_user)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_user_unique_email(self, db_session: Session, test_user: User):
        """メールアドレスの一意性制約テスト"""
        duplicate_user = User(
            username="differentuser",
            email=test_user.email,  # 重複するメールアドレス
            hashed_password=AuthService.hash_password("password123"),
        )
        db_session.add(duplicate_user)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_user_relationship_with_subscriptions(
        self, db_session: Session, test_user: User
    ):
        """ユーザーとサブスクリプションのリレーションテスト"""
        # サブスクリプション追加
        sub1 = Subscription(
            user_id=test_user.id,
            service_name="Spotify",
            monthly_fee=Decimal("980.00"),
            category=SubscriptionCategory.MUSIC,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )
        sub2 = Subscription(
            user_id=test_user.id,
            service_name="YouTube Premium",
            monthly_fee=Decimal("1280.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )
        db_session.add_all([sub1, sub2])
        db_session.commit()

        # リレーションの確認
        db_session.refresh(test_user)
        assert len(test_user.subscriptions) == 2
        assert sub1 in test_user.subscriptions
        assert sub2 in test_user.subscriptions

    def test_user_cascade_delete(self, db_session: Session, test_user: User):
        """ユーザー削除時のカスケード削除テスト"""
        # サブスクリプション追加
        subscription = Subscription(
            user_id=test_user.id,
            service_name="Netflix",
            monthly_fee=Decimal("1980.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )
        db_session.add(subscription)
        db_session.commit()
        subscription_id = subscription.id

        # ユーザー削除
        db_session.delete(test_user)
        db_session.commit()

        # サブスクリプションもカスケード削除されていることを確認
        deleted_subscription = (
            db_session.query(Subscription).filter_by(id=subscription_id).first()
        )
        assert deleted_subscription is None


class TestSubscriptionModel:
    """Subscriptionモデルのテストクラス"""

    def test_create_subscription(self, db_session: Session, test_user: User):
        """サブスクリプション作成テスト"""
        subscription = Subscription(
            user_id=test_user.id,
            service_name="Amazon Prime",
            monthly_fee=Decimal("600.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 15),
            next_renewal_date=date(2024, 2, 15),
            memo="プライム会員",
            is_active=True,
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.id is not None
        assert subscription.user_id == test_user.id
        assert subscription.service_name == "Amazon Prime"
        assert subscription.monthly_fee == Decimal("600.00")
        assert subscription.category == SubscriptionCategory.VIDEO_STREAMING
        assert subscription.start_date == date(2024, 1, 15)
        assert subscription.next_renewal_date == date(2024, 2, 15)
        assert subscription.memo == "プライム会員"
        assert subscription.is_active is True
        assert subscription.created_at is not None
        assert subscription.updated_at is not None

    def test_update_subscription(
        self, db_session: Session, test_subscription: Subscription
    ):
        """サブスクリプション更新テスト"""
        original_updated_at = test_subscription.updated_at

        # 更新
        test_subscription.monthly_fee = Decimal("2200.00")
        test_subscription.memo = "値上げ後"
        db_session.commit()
        db_session.refresh(test_subscription)

        assert test_subscription.monthly_fee == Decimal("2200.00")
        assert test_subscription.memo == "値上げ後"
        # updated_atが更新されていることを確認
        assert test_subscription.updated_at >= original_updated_at

    def test_delete_subscription(
        self, db_session: Session, test_subscription: Subscription
    ):
        """サブスクリプション削除テスト"""
        subscription_id = test_subscription.id

        db_session.delete(test_subscription)
        db_session.commit()

        # 削除されていることを確認
        deleted_subscription = (
            db_session.query(Subscription).filter_by(id=subscription_id).first()
        )
        assert deleted_subscription is None

    def test_subscription_with_all_categories(self, db_session: Session, test_user: User):
        """全カテゴリのサブスクリプション作成テスト"""
        subscriptions = [
            Subscription(
                user_id=test_user.id,
                service_name="Netflix",
                monthly_fee=Decimal("1980.00"),
                category=SubscriptionCategory.VIDEO_STREAMING,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Spotify",
                monthly_fee=Decimal("980.00"),
                category=SubscriptionCategory.MUSIC,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="PlayStation Plus",
                monthly_fee=Decimal("1337.00"),
                category=SubscriptionCategory.GAMING,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Dropbox",
                monthly_fee=Decimal("1500.00"),
                category=SubscriptionCategory.CLOUD,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Notion",
                monthly_fee=Decimal("2000.00"),
                category=SubscriptionCategory.TOOL,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="Kindle Unlimited",
                monthly_fee=Decimal("980.00"),
                category=SubscriptionCategory.MEDIA,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
            Subscription(
                user_id=test_user.id,
                service_name="セゾンプレミアム",
                monthly_fee=Decimal("1100.00"),
                category=SubscriptionCategory.OTHER,
                start_date=date(2024, 1, 1),
                next_renewal_date=date(2024, 2, 1),
            ),
        ]
        db_session.add_all(subscriptions)
        db_session.commit()

        # 全て正しく作成されていることを確認
        saved_subscriptions = db_session.query(Subscription).all()
        assert len(saved_subscriptions) == 7

        categories = [sub.category for sub in saved_subscriptions]
        assert SubscriptionCategory.VIDEO_STREAMING in categories
        assert SubscriptionCategory.MUSIC in categories
        assert SubscriptionCategory.GAMING in categories
        assert SubscriptionCategory.CLOUD in categories
        assert SubscriptionCategory.TOOL in categories
        assert SubscriptionCategory.MEDIA in categories
        assert SubscriptionCategory.OTHER in categories

    def test_subscription_without_memo(self, db_session: Session, test_user: User):
        """メモなしのサブスクリプション作成テスト"""
        subscription = Subscription(
            user_id=test_user.id,
            service_name="Hulu",
            monthly_fee=Decimal("1026.00"),
            category=SubscriptionCategory.VIDEO_STREAMING,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            # memo は指定しない
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.memo is None

    def test_subscription_inactive_status(self, db_session: Session, test_user: User):
        """非アクティブなサブスクリプションのテスト"""
        subscription = Subscription(
            user_id=test_user.id,
            service_name="Apple Music",
            monthly_fee=Decimal("1080.00"),
            category=SubscriptionCategory.MUSIC,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
            is_active=False,  # 非アクティブ
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.is_active is False

    def test_subscription_data_persistence(
        self, db_session: Session, test_subscription: Subscription
    ):
        """データ永続化の検証"""
        subscription_id = test_subscription.id

        # セッションをクリア（キャッシュをクリア）
        db_session.expire_all()

        # データベースから再取得
        reloaded_subscription = (
            db_session.query(Subscription).filter_by(id=subscription_id).first()
        )

        # データが永続化されていることを確認
        assert reloaded_subscription is not None
        assert reloaded_subscription.id == test_subscription.id
        assert reloaded_subscription.service_name == test_subscription.service_name
        assert reloaded_subscription.monthly_fee == test_subscription.monthly_fee
        assert reloaded_subscription.category == test_subscription.category

    def test_subscription_decimal_precision(self, db_session: Session, test_user: User):
        """金額のDecimal精度テスト"""
        subscription = Subscription(
            user_id=test_user.id,
            service_name="Test Service",
            monthly_fee=Decimal("999.99"),  # 小数点以下2桁
            category=SubscriptionCategory.OTHER,
            start_date=date(2024, 1, 1),
            next_renewal_date=date(2024, 2, 1),
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.monthly_fee == Decimal("999.99")
        # Decimal型であることを確認
        assert isinstance(subscription.monthly_fee, Decimal)

    def test_subscription_date_handling(self, db_session: Session, test_user: User):
        """日付の取り扱いテスト"""
        start = date(2024, 1, 1)
        renewal = date(2024, 12, 31)

        subscription = Subscription(
            user_id=test_user.id,
            service_name="Test Service",
            monthly_fee=Decimal("1000.00"),
            category=SubscriptionCategory.OTHER,
            start_date=start,
            next_renewal_date=renewal,
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.start_date == start
        assert subscription.next_renewal_date == renewal
        # date型であることを確認
        assert isinstance(subscription.start_date, date)
        assert isinstance(subscription.next_renewal_date, date)
