"""
セキュリティミドルウェアの単体テスト（タスク9.2）

テスト対象:
- SecurityHeadersMiddleware: XSS・クリックジャッキング防止ヘッダーの付与
- CSRFProtectionMiddleware: 状態変更リクエストのOriginヘッダー検証
- CORSMiddleware: 許可オリジンからのリクエスト制御

TestClient を使用して HTTP レスポンスを検証する。
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.middleware.security import CSRFProtectionMiddleware, SecurityHeadersMiddleware

ALLOWED_ORIGIN = "http://localhost:8501"
DISALLOWED_ORIGIN = "http://evil.example.com"


def _create_test_app(allowed_origins: list[str] | None = None) -> FastAPI:
    """
    セキュリティミドルウェアテスト用の最小 FastAPI アプリを生成する。

    DBやルーターは不要なため、テスト用エンドポイントのみ定義する。
    """
    if allowed_origins is None:
        allowed_origins = [ALLOWED_ORIGIN]

    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(CSRFProtectionMiddleware, allowed_origins=allowed_origins)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/items")
    def get_items() -> dict:
        return {"items": []}

    @app.post("/items")
    def create_item() -> dict:
        return {"created": True}

    @app.put("/items/{item_id}")
    def update_item(item_id: int) -> dict:
        return {"updated": item_id}

    @app.delete("/items/{item_id}")
    def delete_item(item_id: int) -> dict:
        return {"deleted": item_id}

    return app


@pytest.fixture
def client() -> TestClient:
    """テスト用 TestClient フィクスチャ"""
    return TestClient(_create_test_app(), raise_server_exceptions=False)


# ==============================================================================
# SecurityHeadersMiddleware のテスト
# ==============================================================================


class TestSecurityHeadersMiddleware:
    """セキュリティヘッダーが全レスポンスに付与されることを検証"""

    def test_X_Content_Type_Optionsヘッダーが付与される(self, client: TestClient):
        """MIMEスニッフィング防止ヘッダーが nosniff である"""
        response = client.get("/items")

        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_X_Frame_Optionsヘッダーが付与される(self, client: TestClient):
        """クリックジャッキング防止ヘッダーが DENY である"""
        response = client.get("/items")

        assert response.headers["X-Frame-Options"] == "DENY"

    def test_X_XSS_Protectionヘッダーが付与される(self, client: TestClient):
        """XSSフィルターヘッダーが有効になっている"""
        response = client.get("/items")

        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    def test_Content_Security_Policyヘッダーが付与される(self, client: TestClient):
        """CSPヘッダーが付与されている"""
        response = client.get("/items")

        assert "Content-Security-Policy" in response.headers

    def test_Referrer_Policyヘッダーが付与される(self, client: TestClient):
        """Referrer-Policyヘッダーが付与されている"""
        response = client.get("/items")

        assert "Referrer-Policy" in response.headers

    def test_Strict_Transport_Securityヘッダーが付与される(self, client: TestClient):
        """HSTSヘッダーが付与されている"""
        response = client.get("/items")

        assert "Strict-Transport-Security" in response.headers

    def test_POSTレスポンスにもセキュリティヘッダーが付与される(self, client: TestClient):
        """GETだけでなくPOSTのレスポンスにもヘッダーが付与される"""
        response = client.post("/items", headers={"origin": ALLOWED_ORIGIN})

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


# ==============================================================================
# CSRFProtectionMiddleware のテスト
# ==============================================================================


class TestCSRFProtectionMiddleware:
    """CSRFオリジン検証ミドルウェアの動作を検証"""

    def test_許可オリジンからのPOSTは通る(self, client: TestClient):
        """許可リストのオリジンからのPOSTリクエストは正常に処理される"""
        response = client.post("/items", headers={"origin": ALLOWED_ORIGIN})

        assert response.status_code == 200

    def test_許可オリジンからのPUTは通る(self, client: TestClient):
        """許可リストのオリジンからのPUTリクエストは正常に処理される"""
        response = client.put("/items/1", headers={"origin": ALLOWED_ORIGIN})

        assert response.status_code == 200

    def test_許可オリジンからのDELETEは通る(self, client: TestClient):
        """許可リストのオリジンからのDELETEリクエストは正常に処理される"""
        response = client.delete("/items/1", headers={"origin": ALLOWED_ORIGIN})

        assert response.status_code == 200

    def test_不正オリジンからのPOSTは403(self, client: TestClient):
        """許可リストにないオリジンからのPOSTは403で拒否される"""
        response = client.post("/items", headers={"origin": DISALLOWED_ORIGIN})

        assert response.status_code == 403

    def test_不正オリジンからのPUTは403(self, client: TestClient):
        """許可リストにないオリジンからのPUTは403で拒否される"""
        response = client.put("/items/1", headers={"origin": DISALLOWED_ORIGIN})

        assert response.status_code == 403

    def test_不正オリジンからのDELETEは403(self, client: TestClient):
        """許可リストにないオリジンからのDELETEは403で拒否される"""
        response = client.delete("/items/1", headers={"origin": DISALLOWED_ORIGIN})

        assert response.status_code == 403

    def test_403レスポンスのerror_codeがCSRF_FORBIDDEN(self, client: TestClient):
        """403レスポンスの error_code が CSRF_FORBIDDEN である"""
        response = client.post("/items", headers={"origin": DISALLOWED_ORIGIN})

        assert response.json()["error_code"] == "CSRF_FORBIDDEN"

    def test_403レスポンスに日本語メッセージが含まれる(self, client: TestClient):
        """403レスポンスに日本語エラーメッセージが含まれる"""
        response = client.post("/items", headers={"origin": DISALLOWED_ORIGIN})

        assert "許可されていないオリジン" in response.json()["message"]

    def test_Originヘッダーなしのリクエストは通る(self, client: TestClient):
        """Originヘッダーがない場合（curl等の内部呼び出し）は許可される"""
        response = client.post("/items")

        assert response.status_code == 200

    def test_GETリクエストはOrigin検証をスキップ(self, client: TestClient):
        """GETリクエストは読み取り専用なので不正オリジンでも通る"""
        response = client.get("/items", headers={"origin": DISALLOWED_ORIGIN})

        assert response.status_code == 200


# ==============================================================================
# CORSMiddleware のテスト
# ==============================================================================


class TestCORSMiddleware:
    """CORSヘッダーが適切に設定されることを検証"""

    def test_許可オリジンからのプリフライトリクエストが成功(self, client: TestClient):
        """許可リストのオリジンからのOPTIONSリクエストに200が返る"""
        response = client.options(
            "/items",
            headers={
                "origin": ALLOWED_ORIGIN,
                "access-control-request-method": "POST",
            },
        )

        assert response.status_code == 200

    def test_許可オリジンからのリクエストにACACヘッダーが付与される(self, client: TestClient):
        """許可オリジンへのレスポンスにAccess-Control-Allow-Credentialsが付与される"""
        response = client.get("/items", headers={"origin": ALLOWED_ORIGIN})

        assert response.headers.get("access-control-allow-credentials") == "true"
