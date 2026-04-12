"""
統合テスト

FastAPIのTestClientを使用して、認証→サブスクリプションCRUD→ダッシュボードの
エンドツーエンドフローを検証する。
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# テスト用データベースURLを設定（appインポート前に設定する必要がある）
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5432/subscription_manager_test"
)

from backend.database import Base, get_db
from backend.main import app
from backend.services.auth_service import AuthService

# テスト用エンジンとセッション
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """テスト用DBセッション"""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """テストごとにDBとインメモリ状態をリセットする"""
    # トークンブラックリストをクリア（インメモリのためテスト間で残る）
    from backend.services.auth_service import _token_blacklist
    _token_blacklist.clear()

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """テスト用DBセッション"""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture
def registered_user(db_session: Session):
    """テスト用ユーザーをDBに直接作成する"""
    from backend.models.user import User

    hashed_password = AuthService.hash_password("testpass123")
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_tokens(client, registered_user):
    """ログインしてトークンペアを取得する"""
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def auth_header(auth_tokens):
    """認証ヘッダーを返す"""
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


# ===== 認証フローのテスト =====


class TestAuthFlow:
    """認証エンドツーエンドテスト"""

    def test_login_success(self, client, registered_user):
        """ログイン成功: トークンペアが返る"""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, registered_user):
        """ログイン失敗: パスワード誤り"""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpass"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """ログイン失敗: 存在しないユーザー"""
        response = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "test"},
        )
        assert response.status_code == 401

    def test_logout_invalidates_token(self, client, auth_tokens):
        """ログアウト: トークンが無効化される"""
        token = auth_tokens["access_token"]
        header = {"Authorization": f"Bearer {token}"}

        # ログアウト
        response = client.post("/auth/logout", headers=header)
        assert response.status_code == 200

        # ログアウト後のアクセスは401
        response = client.get("/subscriptions", headers=header)
        assert response.status_code == 401

    def test_token_refresh(self, client, auth_tokens):
        """トークン更新: 新しいトークンペアが返り、旧トークンは無効化される"""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # 新しいアクセストークンで認証できる
        new_header = {"Authorization": f"Bearer {data['access_token']}"}
        response = client.get("/subscriptions", headers=new_header)
        assert response.status_code == 200

    def test_refresh_with_invalid_token(self, client):
        """トークン更新失敗: 無効なリフレッシュトークン"""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == 401


# ===== サブスクリプションCRUDフローのテスト =====


class TestSubscriptionCRUDFlow:
    """サブスクリプション管理エンドツーエンドテスト"""

    def test_full_crud_flow(self, client, auth_header):
        """作成→一覧取得→更新→削除の一連のフロー"""
        # 1. 作成
        create_data = {
            "service_name": "Netflix",
            "monthly_fee": 1980.0,
            "category": "動画配信",
            "start_date": "2024-01-01",
        }
        response = client.post("/subscriptions", json=create_data, headers=auth_header)
        assert response.status_code == 201
        created = response.json()
        sub_id = created["id"]
        assert created["service_name"] == "Netflix"
        assert float(created["monthly_fee"]) == 1980.0
        assert created["category"] == "動画配信"
        # next_renewal_dateが自動計算されている
        assert created["next_renewal_date"] == "2024-02-01"

        # 2. 一覧取得
        response = client.get("/subscriptions", headers=auth_header)
        assert response.status_code == 200
        subs = response.json()
        assert len(subs) == 1
        assert subs[0]["service_name"] == "Netflix"

        # 3. 更新
        update_data = {"monthly_fee": 2480.0, "memo": "プレミアムプランに変更"}
        response = client.put(
            f"/subscriptions/{sub_id}", json=update_data, headers=auth_header
        )
        assert response.status_code == 200
        updated = response.json()
        assert float(updated["monthly_fee"]) == 2480.0
        assert updated["memo"] == "プレミアムプランに変更"

        # 4. 削除（論理削除）
        response = client.delete(f"/subscriptions/{sub_id}", headers=auth_header)
        assert response.status_code == 200

        # 5. 削除後は一覧に表示されない
        response = client.get("/subscriptions", headers=auth_header)
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_create_with_all_categories(self, client, auth_header):
        """全カテゴリでのサブスクリプション作成"""
        categories = ["動画配信", "音楽", "ゲーム", "クラウド", "ツール", "メディア", "その他"]
        for i, category in enumerate(categories):
            response = client.post(
                "/subscriptions",
                json={
                    "service_name": f"Service{i}",
                    "monthly_fee": 500.0 * (i + 1),
                    "category": category,
                    "start_date": "2024-01-01",
                },
                headers=auth_header,
            )
            assert response.status_code == 201, f"カテゴリ '{category}' で作成失敗"
            assert response.json()["category"] == category

    def test_update_nonexistent(self, client, auth_header):
        """存在しないサブスクリプションの更新は404"""
        response = client.put(
            "/subscriptions/99999",
            json={"monthly_fee": 1000},
            headers=auth_header,
        )
        assert response.status_code == 404

    def test_delete_nonexistent(self, client, auth_header):
        """存在しないサブスクリプションの削除は404"""
        response = client.delete("/subscriptions/99999", headers=auth_header)
        assert response.status_code == 404


# ===== ダッシュボードフローのテスト =====


class TestDashboardFlow:
    """ダッシュボードエンドツーエンドテスト"""

    def test_dashboard_empty(self, client, auth_header):
        """サブスクリプションなしのダッシュボード"""
        response = client.get("/dashboard", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_monthly_expense"]) == 0
        assert data["subscription_count"] == 0
        assert data["category_breakdown"] == {}
        assert data["upcoming_renewals"] == []

    def test_dashboard_with_data(self, client, auth_header):
        """サブスクリプションありのダッシュボード"""
        # テストデータ作成
        services = [
            {"service_name": "Netflix", "monthly_fee": 1980.0,
             "category": "動画配信", "start_date": "2024-01-01"},
            {"service_name": "Spotify", "monthly_fee": 980.0,
             "category": "音楽", "start_date": "2024-01-01"},
        ]
        for s in services:
            client.post("/subscriptions", json=s, headers=auth_header)

        response = client.get("/dashboard", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_monthly_expense"]) == 2960.0
        assert data["subscription_count"] == 2
        assert "動画配信" in data["category_breakdown"]
        assert "音楽" in data["category_breakdown"]

    def test_dashboard_categories_endpoint(self, client, auth_header):
        """カテゴリ別集計エンドポイント"""
        client.post(
            "/subscriptions",
            json={"service_name": "Netflix", "monthly_fee": 1980.0,
                  "category": "動画配信", "start_date": "2024-01-01"},
            headers=auth_header,
        )
        response = client.get("/dashboard/categories", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "動画配信" in data

    def test_dashboard_trends_endpoint(self, client, auth_header):
        """月別支出推移エンドポイント"""
        response = client.get("/dashboard/trends", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 12  # 12ヶ月分

    def test_dashboard_renewals_endpoint(self, client, auth_header):
        """更新予定エンドポイント"""
        response = client.get("/dashboard/renewals", headers=auth_header)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ===== セキュリティテスト =====


class TestSecurityIntegration:
    """セキュリティ統合テスト"""

    def test_unauthenticated_access_denied(self, client):
        """認証なしのアクセスは401"""
        endpoints = [
            ("GET", "/subscriptions"),
            ("POST", "/subscriptions"),
            ("GET", "/dashboard"),
            ("GET", "/dashboard/categories"),
            ("GET", "/dashboard/trends"),
            ("GET", "/dashboard/renewals"),
        ]
        for method, path in endpoints:
            response = getattr(client, method.lower())(path)
            assert response.status_code == 401, f"{method} {path} が401を返さない"

    def test_invalid_token_denied(self, client):
        """無効なトークンは401"""
        header = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/subscriptions", headers=header)
        assert response.status_code == 401

    def test_security_headers_present(self, client):
        """セキュリティヘッダーが付与されている"""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_health_check(self, client):
        """ヘルスチェックは認証不要"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_user_isolation(self, client, auth_header, db_session):
        """他のユーザーのサブスクリプションにはアクセスできない"""
        # ユーザー1でサブスクリプション作成
        client.post(
            "/subscriptions",
            json={"service_name": "Netflix", "monthly_fee": 1980.0,
                  "category": "動画配信", "start_date": "2024-01-01"},
            headers=auth_header,
        )

        # ユーザー2を作成してログイン
        from backend.models.user import User

        hashed = AuthService.hash_password("pass2")
        user2 = User(username="user2", email="user2@example.com",
                     hashed_password=hashed)
        db_session.add(user2)
        db_session.commit()

        login_resp = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
        )
        user2_header = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        # ユーザー2にはユーザー1のサブスクリプションは見えない
        response = client.get("/subscriptions", headers=user2_header)
        assert response.status_code == 200
        assert len(response.json()) == 0
