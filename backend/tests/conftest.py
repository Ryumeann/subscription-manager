"""
pytest設定とテストフィクスチャ

テストデータベースの設定、モックサービス、共通フィクスチャを提供する。
"""

import os
from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import Settings, get_settings
from backend.database import Base
from backend.models.subscription import Subscription
from backend.models.subscription_category import SubscriptionCategory
from backend.models.user import User
from backend.services.auth_service import AuthService

# テスト用の環境変数設定
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5432/subscription_manager_test"
)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """
    テスト用設定フィクスチャ。

    テスト専用のデータベースURLや認証設定を提供する。
    """
    return Settings(
        database_url="postgresql://postgres:postgres@localhost:5432/subscription_manager_test",
        secret_key="test-secret-key",
        algorithm="HS256",
        access_token_expire_hours=24,
        refresh_token_expire_days=30,
        app_env="testing",
        debug=True,
    )


@pytest.fixture(scope="session")
def engine(test_settings: Settings):
    """
    テスト用SQLAlchemyエンジンフィクスチャ（セッションスコープ）。

    全テストセッションで共有するデータベースエンジンを作成する。
    """
    return create_engine(test_settings.database_url, pool_pre_ping=True)


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """
    テスト用データベースセッションフィクスチャ（関数スコープ）。

    各テスト関数ごとに新しいセッションを作成し、テーブルを初期化する。
    テスト終了後はロールバックしてクリーンアップする。
    """
    # テーブル作成
    Base.metadata.create_all(bind=engine)

    # セッション作成
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # テーブル削除（各テスト後にクリーンアップ）
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """
    テスト用ユーザーフィクスチャ。

    パスワードがハッシュ化されたテストユーザーを作成する。
    平文パスワード: "testpassword123"
    """
    hashed_password = AuthService.hash_password("testpassword123")
    user = User(
        username="testuser",
        hashed_password=hashed_password,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_subscription(db_session: Session, test_user: User) -> Subscription:
    """
    テスト用サブスクリプションフィクスチャ。

    テストユーザーに紐づくサンプルサブスクリプションを作成する。
    """
    subscription = Subscription(
        user_id=test_user.id,
        service_name="Netflix",
        monthly_fee=Decimal("1980.00"),
        category=SubscriptionCategory.VIDEO_STREAMING,
        start_date=date(2024, 1, 1),
        next_renewal_date=date(2024, 2, 1),
        memo="テスト用サブスクリプション",
        is_active=True,
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


@pytest.fixture
def auth_service(db_session: Session) -> AuthService:
    """認証サービスフィクスチャ"""
    return AuthService(db_session)


# moto設定用のフィクスチャ（タスク8.2で使用）
@pytest.fixture(scope="function")
def aws_credentials():
    """
    moto用のAWS認証情報をモック化するフィクスチャ。

    AWSサービスのモックテスト時に使用する。
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"
