"""
グローバルエラーハンドラーの単体テスト（タスク8.4）

テスト対象:
- HTTPException → ErrorResponse（日本語メッセージ・error_code）
- RequestValidationError → ErrorResponse（422・バリデーション詳細）
- 予期しない Exception → ErrorResponse（500・内部詳細を隠蔽）

TestClient を使用して実際の HTTP レスポンスを検証する。
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.error_handlers import register_error_handlers


def _create_test_app() -> FastAPI:
    """
    エラーハンドラーテスト用の最小 FastAPI アプリを生成する。

    実際のDBやルーターは不要なため、テスト用エンドポイントのみ定義する。
    """
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise-404")
    def raise_404() -> dict:
        raise HTTPException(status_code=404, detail="サブスクリプションが見つかりません")

    @app.get("/raise-401")
    def raise_401() -> dict:
        raise HTTPException(status_code=401, detail="認証が必要です")

    @app.get("/raise-500")
    def raise_500() -> dict:
        raise RuntimeError("予期しない内部エラー")

    class ItemRequest(BaseModel):
        value: int

    @app.post("/validate")
    def validate_item(item: ItemRequest) -> dict:
        return {"value": item.value}

    return app


@pytest.fixture
def client() -> TestClient:
    """テスト用 TestClient フィクスチャ（サーバー例外を再送出しない）"""
    return TestClient(_create_test_app(), raise_server_exceptions=False)


# ==============================================================================
# ErrorResponse 形式の共通検証
# ==============================================================================


def _assert_error_response_shape(data: dict) -> None:
    """ErrorResponse の必須フィールドが存在することを確認する"""
    assert "error_code" in data
    assert "message" in data
    assert "timestamp" in data
    assert "request_id" in data


# ==============================================================================
# HTTPException ハンドラーのテスト
# ==============================================================================


class TestHttpExceptionHandler:
    """HTTPException → ErrorResponse 変換テスト"""

    def test_404がErrorResponse形式で返る(self, client: TestClient):
        """404 HTTPException が ErrorResponse 形式になる"""
        response = client.get("/raise-404")

        assert response.status_code == 404
        data = response.json()
        _assert_error_response_shape(data)

    def test_404のerror_codeがHTTP_404(self, client: TestClient):
        """404 の error_code が "HTTP_404" になる"""
        response = client.get("/raise-404")

        assert response.json()["error_code"] == "HTTP_404"

    def test_404の日本語メッセージが保持される(self, client: TestClient):
        """raise HTTPException の detail（日本語）がそのまま message に入る"""
        response = client.get("/raise-404")

        assert response.json()["message"] == "サブスクリプションが見つかりません"

    def test_401がErrorResponse形式で返る(self, client: TestClient):
        """401 HTTPException が ErrorResponse 形式になる"""
        response = client.get("/raise-401")

        assert response.status_code == 401
        assert response.json()["error_code"] == "HTTP_401"
        assert response.json()["message"] == "認証が必要です"

    def test_request_idがUUID形式(self, client: TestClient):
        """request_id が UUID 形式の文字列である"""
        import re

        response = client.get("/raise-404")
        request_id = response.json()["request_id"]

        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, request_id)

    def test_timestampが含まれる(self, client: TestClient):
        """timestamp フィールドが ISO 形式の文字列として含まれる"""
        from datetime import datetime

        response = client.get("/raise-404")
        timestamp = response.json()["timestamp"]

        # Python 3.10 は "Z" サフィックス非対応のため "+00:00" に変換してパース
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt is not None


# ==============================================================================
# RequestValidationError ハンドラーのテスト
# ==============================================================================


class TestValidationExceptionHandler:
    """RequestValidationError → ErrorResponse 変換テスト"""

    def test_バリデーションエラーが422で返る(self, client: TestClient):
        """不正なリクエストボディは 422 で返る"""
        response = client.post("/validate", json={"value": "文字列はNG"})

        assert response.status_code == 422

    def test_error_codeがVALIDATION_ERROR(self, client: TestClient):
        """バリデーションエラーの error_code が VALIDATION_ERROR になる"""
        response = client.post("/validate", json={"value": "文字列はNG"})

        assert response.json()["error_code"] == "VALIDATION_ERROR"

    def test_日本語メッセージが返る(self, client: TestClient):
        """バリデーションエラー時に日本語メッセージが返る"""
        response = client.post("/validate", json={"value": "文字列はNG"})

        assert response.json()["message"] == "入力データが正しくありません"

    def test_detailsにエラー詳細が含まれる(self, client: TestClient):
        """details.errors にバリデーションエラーの詳細が含まれる"""
        response = client.post("/validate", json={"value": "文字列はNG"})

        data = response.json()
        assert "details" in data
        assert "errors" in data["details"]
        assert isinstance(data["details"]["errors"], list)
        assert len(data["details"]["errors"]) > 0

    def test_ErrorResponse形式の共通フィールドが含まれる(self, client: TestClient):
        """timestamp と request_id が含まれる"""
        response = client.post("/validate", json={"value": "文字列はNG"})

        _assert_error_response_shape(response.json())


# ==============================================================================
# 汎用例外ハンドラーのテスト
# ==============================================================================


class TestGenericExceptionHandler:
    """予期しない Exception → 500 ErrorResponse 変換テスト"""

    def test_予期しないエラーが500で返る(self, client: TestClient):
        """RuntimeError などは 500 で返る"""
        response = client.get("/raise-500")

        assert response.status_code == 500

    def test_error_codeがINTERNAL_SERVER_ERROR(self, client: TestClient):
        """error_code が INTERNAL_SERVER_ERROR になる"""
        response = client.get("/raise-500")

        assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"

    def test_日本語メッセージが返る(self, client: TestClient):
        """内部エラーでも日本語メッセージが返る"""
        response = client.get("/raise-500")

        assert "サーバー内部エラーが発生しました" in response.json()["message"]

    def test_内部エラー詳細が隠蔽される(self, client: TestClient):
        """RuntimeError のメッセージがレスポンスに含まれない（情報漏洩防止）"""
        response = client.get("/raise-500")

        assert "予期しない内部エラー" not in response.json()["message"]

    def test_ErrorResponse形式の共通フィールドが含まれる(self, client: TestClient):
        """timestamp と request_id が含まれる"""
        response = client.get("/raise-500")

        _assert_error_response_shape(response.json())
