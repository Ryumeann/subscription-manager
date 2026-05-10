"""
APIクライアント

FastAPIバックエンドへのHTTPリクエストを管理するクライアントクラス。
"""
from typing import Any, Optional

import requests

API_BASE_URL = "http://localhost:8000"


class APIError(Exception):
    """APIエラー例外"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class APIClient:
    """バックエンドAPIクライアント"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url

    def _headers(self, token: Optional[str] = None) -> dict:
        """リクエストヘッダーを生成する"""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _handle_response(self, response: requests.Response) -> Any:
        """レスポンスを処理し、エラー時は例外を発生させる"""
        if response.ok:
            if not response.content:
                return {}
            return response.json()
        try:
            detail = response.json().get("detail", "エラーが発生しました")
        except Exception:
            detail = "エラーが発生しました"
        raise APIError(response.status_code, str(detail))

    def login(self, username: str, password: str) -> dict:
        """ログイン - アクセストークンとリフレッシュトークンを返す"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
        )
        return self._handle_response(response)

    def register(self, username: str, password: str) -> dict:
        """新規ユーザー登録 - 成功時はトークンペアを返す（自動ログイン扱い）"""
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={
                "username": username,
                "password": password,
            },
        )
        return self._handle_response(response)

    def logout(self, token: str) -> dict:
        """ログアウト - トークンをブラックリストに追加する"""
        response = requests.post(
            f"{self.base_url}/auth/logout",
            headers=self._headers(token),
        )
        return self._handle_response(response)

    def refresh_token(self, refresh_token: str) -> dict:
        """トークン更新 - 新しいアクセストークンとリフレッシュトークンを返す"""
        response = requests.post(
            f"{self.base_url}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        return self._handle_response(response)

    def get_subscriptions(self, token: str) -> list:
        """サブスクリプション一覧を取得する"""
        response = requests.get(
            f"{self.base_url}/subscriptions",
            headers=self._headers(token),
        )
        return self._handle_response(response)

    def create_subscription(self, token: str, data: dict) -> dict:
        """新規サブスクリプションを作成する"""
        response = requests.post(
            f"{self.base_url}/subscriptions",
            json=data,
            headers=self._headers(token),
        )
        return self._handle_response(response)

    def update_subscription(self, token: str, subscription_id: int, data: dict) -> dict:
        """サブスクリプションを更新する"""
        response = requests.put(
            f"{self.base_url}/subscriptions/{subscription_id}",
            json=data,
            headers=self._headers(token),
        )
        return self._handle_response(response)

    def delete_subscription(self, token: str, subscription_id: int) -> dict:
        """サブスクリプションを削除する（論理削除）"""
        response = requests.delete(
            f"{self.base_url}/subscriptions/{subscription_id}",
            headers=self._headers(token),
        )
        return self._handle_response(response)

    def get_dashboard(self, token: str) -> dict:
        """ダッシュボードデータを取得する"""
        response = requests.get(
            f"{self.base_url}/dashboard",
            headers=self._headers(token),
        )
        return self._handle_response(response)
