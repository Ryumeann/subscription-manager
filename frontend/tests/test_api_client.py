"""
APIクライアントの単体テスト

APIClient のHTTPリクエストとレスポンス処理をモックを使ってテストする。
"""

from unittest.mock import MagicMock, patch

import pytest

import sys
import os

# frontendディレクトリをパスに追加（api_client をインポートするため）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api_client import APIClient, APIError


@pytest.fixture
def client():
    """テスト用APIクライアント"""
    return APIClient(base_url="http://testserver")


class TestAPIClientHeaders:
    """ヘッダー生成のテスト"""

    def test_headers_without_token(self, client):
        """トークンなしの場合、Content-Typeのみ"""
        headers = client._headers()
        assert headers == {"Content-Type": "application/json"}

    def test_headers_with_token(self, client):
        """トークンありの場合、Authorizationヘッダーが追加される"""
        headers = client._headers("test-token")
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"


class TestAPIClientHandleResponse:
    """レスポンス処理のテスト"""

    def test_success_response_with_json(self, client):
        """正常レスポンス（JSONあり）"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"key": "value"}'
        mock_response.json.return_value = {"key": "value"}

        result = client._handle_response(mock_response)
        assert result == {"key": "value"}

    def test_success_response_without_content(self, client):
        """正常レスポンス（コンテンツなし = 空dict）"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b""

        result = client._handle_response(mock_response)
        assert result == {}

    def test_error_response_with_detail(self, client):
        """エラーレスポンス（detail付き）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "認証エラー"}

        with pytest.raises(APIError) as exc_info:
            client._handle_response(mock_response)
        assert exc_info.value.status_code == 401
        assert "認証エラー" in exc_info.value.message

    def test_error_response_without_detail(self, client):
        """エラーレスポンス（JSON解析失敗）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("JSON解析失敗")

        with pytest.raises(APIError) as exc_info:
            client._handle_response(mock_response)
        assert exc_info.value.status_code == 500
        assert "エラーが発生しました" in exc_info.value.message


class TestAPIClientLogin:
    """ログインのテスト"""

    @patch("api_client.requests.post")
    def test_login_success(self, mock_post, client):
        """ログイン成功"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"access_token": "abc", "refresh_token": "xyz"}'
        mock_response.json.return_value = {
            "access_token": "abc",
            "refresh_token": "xyz",
            "token_type": "bearer",
        }
        mock_post.return_value = mock_response

        result = client.login("admin", "password")
        assert result["access_token"] == "abc"
        assert result["refresh_token"] == "xyz"

        # 正しいURLとペイロードで呼ばれたか確認
        mock_post.assert_called_once_with(
            "http://testserver/auth/login",
            json={"username": "admin", "password": "password"},
        )

    @patch("api_client.requests.post")
    def test_login_failure(self, mock_post, client):
        """ログイン失敗（401）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "認証失敗"}
        mock_post.return_value = mock_response

        with pytest.raises(APIError) as exc_info:
            client.login("admin", "wrong")
        assert exc_info.value.status_code == 401


class TestAPIClientRegister:
    """新規登録のテスト"""

    @patch("api_client.requests.post")
    def test_register_success(self, mock_post, client):
        """新規登録成功"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"access_token": "abc", "refresh_token": "xyz"}'
        mock_response.json.return_value = {
            "access_token": "abc",
            "refresh_token": "xyz",
            "token_type": "bearer",
        }
        mock_post.return_value = mock_response

        result = client.register("newuser", "Pass1234")
        assert result["access_token"] == "abc"
        assert result["refresh_token"] == "xyz"

        # 正しいURLとペイロードで呼ばれたか確認
        mock_post.assert_called_once_with(
            "http://testserver/auth/register",
            json={
                "username": "newuser",
                "password": "Pass1234",
            },
        )

    @patch("api_client.requests.post")
    def test_register_duplicate_username(self, mock_post, client):
        """登録失敗（ユーザー名重複・409）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "このユーザー名は既に使われています"}
        mock_post.return_value = mock_response

        with pytest.raises(APIError) as exc_info:
            client.register("admin", "Pass1234")
        assert exc_info.value.status_code == 409

    @patch("api_client.requests.post")
    def test_register_validation_error(self, mock_post, client):
        """登録失敗（バリデーションエラー・422）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": "入力データが正しくありません"}
        mock_post.return_value = mock_response

        with pytest.raises(APIError) as exc_info:
            client.register("a", "weak")
        assert exc_info.value.status_code == 422


class TestAPIClientLogout:
    """ログアウトのテスト"""

    @patch("api_client.requests.post")
    def test_logout_success(self, mock_post, client):
        """ログアウト成功"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"message": "ok"}'
        mock_response.json.return_value = {"message": "ok"}
        mock_post.return_value = mock_response

        result = client.logout("token123")
        assert result["message"] == "ok"

        # Authorizationヘッダー付きで呼ばれたか確認
        call_kwargs = mock_post.call_args
        assert "Bearer token123" in str(call_kwargs)


class TestAPIClientRefreshToken:
    """トークン更新のテスト"""

    @patch("api_client.requests.post")
    def test_refresh_success(self, mock_post, client):
        """トークン更新成功"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"access_token": "new_access", "refresh_token": "new_refresh"}'
        mock_response.json.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
        }
        mock_post.return_value = mock_response

        result = client.refresh_token("old_refresh")
        assert result["access_token"] == "new_access"
        assert result["refresh_token"] == "new_refresh"

    @patch("api_client.requests.post")
    def test_refresh_failure(self, mock_post, client):
        """トークン更新失敗（無効なリフレッシュトークン）"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "無効なトークン"}
        mock_post.return_value = mock_response

        with pytest.raises(APIError) as exc_info:
            client.refresh_token("invalid")
        assert exc_info.value.status_code == 401


class TestAPIClientSubscriptions:
    """サブスクリプションCRUDのテスト"""

    @patch("api_client.requests.get")
    def test_get_subscriptions(self, mock_get, client):
        """サブスクリプション一覧取得"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'[{"id": 1}]'
        mock_response.json.return_value = [{"id": 1, "service_name": "Netflix"}]
        mock_get.return_value = mock_response

        result = client.get_subscriptions("token")
        assert len(result) == 1
        assert result[0]["service_name"] == "Netflix"

    @patch("api_client.requests.post")
    def test_create_subscription(self, mock_post, client):
        """サブスクリプション作成"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"id": 1}'
        mock_response.json.return_value = {"id": 1, "service_name": "Spotify"}
        mock_post.return_value = mock_response

        result = client.create_subscription("token", {"service_name": "Spotify"})
        assert result["service_name"] == "Spotify"

    @patch("api_client.requests.put")
    def test_update_subscription(self, mock_put, client):
        """サブスクリプション更新"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"id": 1}'
        mock_response.json.return_value = {"id": 1, "monthly_fee": "1500.00"}
        mock_put.return_value = mock_response

        result = client.update_subscription("token", 1, {"monthly_fee": 1500})
        assert result["monthly_fee"] == "1500.00"

        # URLにサブスクリプションIDが含まれるか確認
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        assert "/subscriptions/1" in call_args[0][0]

    @patch("api_client.requests.delete")
    def test_delete_subscription(self, mock_delete, client):
        """サブスクリプション削除"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"message": "deleted"}'
        mock_response.json.return_value = {"message": "deleted"}
        mock_delete.return_value = mock_response

        result = client.delete_subscription("token", 1)
        assert result["message"] == "deleted"

    @patch("api_client.requests.get")
    def test_get_dashboard(self, mock_get, client):
        """ダッシュボードデータ取得"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'{"total_monthly_expense": 5000}'
        mock_response.json.return_value = {"total_monthly_expense": 5000}
        mock_get.return_value = mock_response

        result = client.get_dashboard("token")
        assert result["total_monthly_expense"] == 5000


class TestAPIError:
    """APIError例外のテスト"""

    def test_api_error_attributes(self):
        """APIErrorのステータスコードとメッセージ"""
        error = APIError(404, "見つかりません")
        assert error.status_code == 404
        assert error.message == "見つかりません"
        assert str(error) == "見つかりません"

    def test_api_error_is_exception(self):
        """APIErrorはExceptionを継承している"""
        error = APIError(500, "サーバーエラー")
        assert isinstance(error, Exception)
