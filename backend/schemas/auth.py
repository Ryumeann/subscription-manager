"""
認証関連のPydanticスキーマ

ログイン・新規登録・トークン更新のリクエスト/レスポンスデータ構造を定義。
"""

import re

from pydantic import BaseModel, Field, field_validator

# ユーザー名のパターン: 英数字 + アンダースコア + ハイフン
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class LoginRequest(BaseModel):
    """ログインリクエストスキーマ"""

    username: str = Field(..., min_length=1, description="ユーザー名")
    password: str = Field(..., min_length=1, description="パスワード")


class RegisterRequest(BaseModel):
    """
    新規ユーザー登録リクエストスキーマ

    バリデーションルール:
    - username: 3〜50文字、英数字・アンダースコア・ハイフンのみ
    - password: 8文字以上、大文字・小文字・数字を各1文字以上含む
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="ユーザー名（3〜50文字、英数字・_・-のみ）",
    )
    password: str = Field(..., min_length=8, description="パスワード（8文字以上）")

    @field_validator("username")
    @classmethod
    def _validate_username_chars(cls, v: str) -> str:
        """ユーザー名は英数字・アンダースコア・ハイフンのみ許可する"""
        if not _USERNAME_PATTERN.match(v):
            raise ValueError(
                "ユーザー名は半角英数字・アンダースコア（_）・ハイフン（-）のみ使用できます"
            )
        return v

    @field_validator("password")
    @classmethod
    def _validate_password_complexity(cls, v: str) -> str:
        """パスワードに大文字・小文字・数字が各1文字以上含まれることを検証する"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("パスワードには大文字英字を1文字以上含めてください")
        if not re.search(r"[a-z]", v):
            raise ValueError("パスワードには小文字英字を1文字以上含めてください")
        if not re.search(r"[0-9]", v):
            raise ValueError("パスワードには数字を1文字以上含めてください")
        return v


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
