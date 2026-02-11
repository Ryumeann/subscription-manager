"""
認証関連のPydanticスキーマ

ログイン・トークン更新のリクエスト/レスポンスデータ構造を定義。
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """ログインリクエストスキーマ"""

    username: str = Field(..., min_length=1, description="ユーザー名")
    password: str = Field(..., min_length=1, description="パスワード")


class TokenResponse(BaseModel):
    """トークンレスポンススキーマ"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """トークン更新リクエストスキーマ"""

    refresh_token: str = Field(..., description="リフレッシュトークン")


class TokenData(BaseModel):
    """JWTトークンのペイロードデータ"""

    user_id: int
    token_type: str  # "access" または "refresh"
