"""
認証システムの単体テスト

AuthServiceのJWT認証、パスワードハッシュ化、トークン管理機能をテストする。
"""

import time
from datetime import timedelta

import pytest
from jose import jwt
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.user import User
from backend.services.auth_service import AuthService, _token_blacklist

settings = get_settings()


class TestPasswordHashing:
    """パスワードハッシュ化のテスト"""

    def test_hash_password(self):
        """パスワードをハッシュ化できる"""
        password = "mypassword123"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        # bcryptハッシュの形式確認（$2b$で始まる）
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """正しいパスワードの検証が成功する"""
        password = "mypassword123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """誤ったパスワードの検証が失敗する"""
        password = "mypassword123"
        wrong_password = "wrongpassword"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(wrong_password, hashed) is False

    def test_hash_different_for_same_password(self):
        """同じパスワードでも異なるハッシュが生成される（ソルト）"""
        password = "mypassword123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2
        # どちらも検証は成功する
        assert AuthService.verify_password(password, hash1) is True
        assert AuthService.verify_password(password, hash2) is True


class TestUserAuthentication:
    """ユーザー認証のテスト"""

    def test_authenticate_user_success(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """正しい認証情報でユーザー認証が成功する"""
        authenticated_user = auth_service.authenticate_user(
            "testuser", "testpassword123"
        )

        assert authenticated_user is not None
        assert authenticated_user.id == test_user.id
        assert authenticated_user.username == test_user.username

    def test_authenticate_user_wrong_password(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """誤ったパスワードで認証が失敗する"""
        authenticated_user = auth_service.authenticate_user(
            "testuser", "wrongpassword"
        )

        assert authenticated_user is None

    def test_authenticate_user_nonexistent_username(
        self, db_session: Session, auth_service: AuthService
    ):
        """存在しないユーザー名で認証が失敗する"""
        authenticated_user = auth_service.authenticate_user(
            "nonexistentuser", "anypassword"
        )

        assert authenticated_user is None

    def test_authenticate_user_empty_password(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """空のパスワードで認証が失敗する"""
        authenticated_user = auth_service.authenticate_user("testuser", "")

        assert authenticated_user is None


class TestTokenGeneration:
    """トークン生成のテスト"""

    def test_create_access_token(self):
        """アクセストークンが正しく生成される"""
        user_id = 1
        token = AuthService.create_access_token(user_id)

        assert token is not None
        assert len(token) > 0

        # トークンをデコードして内容確認
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_custom_expiration(self):
        """カスタム有効期限でアクセストークンを生成"""
        user_id = 1
        expires_delta = timedelta(hours=1)
        token = AuthService.create_access_token(user_id, expires_delta)

        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """リフレッシュトークンが正しく生成される"""
        user_id = 1
        token = AuthService.create_refresh_token(user_id)

        assert token is not None
        assert len(token) > 0

        # トークンをデコードして内容確認
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_create_refresh_token_custom_expiration(self):
        """カスタム有効期限でリフレッシュトークンを生成"""
        user_id = 1
        expires_delta = timedelta(days=7)
        token = AuthService.create_refresh_token(user_id, expires_delta)

        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["type"] == "refresh"

    def test_tokens_are_different(self):
        """アクセストークンとリフレッシュトークンは異なる"""
        user_id = 1
        access_token = AuthService.create_access_token(user_id)
        refresh_token = AuthService.create_refresh_token(user_id)

        assert access_token != refresh_token


class TestTokenVerification:
    """トークン検証のテスト"""

    def setup_method(self):
        """各テストメソッド前にブラックリストをクリア"""
        _token_blacklist.clear()

    def test_verify_valid_access_token(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """有効なアクセストークンの検証が成功する"""
        token = AuthService.create_access_token(test_user.id)
        verified_user = auth_service.verify_token(token)

        assert verified_user is not None
        assert verified_user.id == test_user.id

    def test_verify_invalid_token_signature(
        self, db_session: Session, auth_service: AuthService
    ):
        """無効な署名のトークンは拒否される"""
        # 異なるシークレットキーで署名されたトークン
        fake_token = jwt.encode(
            {"sub": "1", "type": "access"}, "wrong-secret", algorithm="HS256"
        )
        verified_user = auth_service.verify_token(fake_token)

        assert verified_user is None

    def test_verify_malformed_token(
        self, db_session: Session, auth_service: AuthService
    ):
        """不正な形式のトークンは拒否される"""
        verified_user = auth_service.verify_token("not.a.valid.token")

        assert verified_user is None

    def test_verify_expired_token(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """期限切れトークンは拒否される"""
        # 負の有効期限で期限切れトークンを作成
        expired_token = AuthService.create_access_token(
            test_user.id, expires_delta=timedelta(seconds=-1)
        )
        verified_user = auth_service.verify_token(expired_token)

        assert verified_user is None

    def test_verify_refresh_token_as_access_token(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """リフレッシュトークンはアクセストークンとして使用できない"""
        refresh_token = AuthService.create_refresh_token(test_user.id)
        verified_user = auth_service.verify_token(refresh_token)

        assert verified_user is None

    def test_verify_token_for_nonexistent_user(
        self, db_session: Session, auth_service: AuthService
    ):
        """存在しないユーザーのトークンは拒否される"""
        # 存在しないユーザーIDでトークン生成
        token = AuthService.create_access_token(99999)
        verified_user = auth_service.verify_token(token)

        assert verified_user is None

    def test_verify_token_without_sub_claim(
        self, db_session: Session, auth_service: AuthService
    ):
        """sub（ユーザーID）クレームがないトークンは拒否される"""
        token = jwt.encode(
            {"type": "access"}, settings.secret_key, algorithm=settings.algorithm
        )
        verified_user = auth_service.verify_token(token)

        assert verified_user is None

    def test_verify_token_with_invalid_user_id_format(
        self, db_session: Session, auth_service: AuthService
    ):
        """無効なユーザーID形式のトークンは拒否される"""
        token = jwt.encode(
            {"sub": "not-a-number", "type": "access"},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        verified_user = auth_service.verify_token(token)

        assert verified_user is None


class TestRefreshAccessToken:
    """アクセストークン更新のテスト"""

    def setup_method(self):
        """各テストメソッド前にブラックリストをクリア"""
        _token_blacklist.clear()

    def test_refresh_access_token_success(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """有効なリフレッシュトークンで新しいアクセストークンを取得"""
        refresh_token = AuthService.create_refresh_token(test_user.id)
        new_access_token = auth_service.refresh_access_token(refresh_token)

        assert new_access_token is not None
        assert len(new_access_token) > 0

        # 新しいアクセストークンで検証が成功する
        verified_user = auth_service.verify_token(new_access_token)
        assert verified_user is not None
        assert verified_user.id == test_user.id

    def test_refresh_access_token_with_access_token_fails(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """アクセストークンでリフレッシュはできない"""
        access_token = AuthService.create_access_token(test_user.id)
        new_access_token = auth_service.refresh_access_token(access_token)

        assert new_access_token is None

    def test_refresh_access_token_invalid_token(
        self, db_session: Session, auth_service: AuthService
    ):
        """無効なリフレッシュトークンは拒否される"""
        new_access_token = auth_service.refresh_access_token("invalid.token")

        assert new_access_token is None

    def test_refresh_access_token_expired(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """期限切れリフレッシュトークンは拒否される"""
        expired_refresh_token = AuthService.create_refresh_token(
            test_user.id, expires_delta=timedelta(seconds=-1)
        )
        new_access_token = auth_service.refresh_access_token(expired_refresh_token)

        assert new_access_token is None

    def test_refresh_access_token_for_nonexistent_user(
        self, db_session: Session, auth_service: AuthService
    ):
        """存在しないユーザーのリフレッシュトークンは拒否される"""
        refresh_token = AuthService.create_refresh_token(99999)
        new_access_token = auth_service.refresh_access_token(refresh_token)

        assert new_access_token is None


class TestTokenBlacklist:
    """トークンブラックリストのテスト"""

    def setup_method(self):
        """各テストメソッド前にブラックリストをクリア"""
        _token_blacklist.clear()

    def test_blacklist_token(self):
        """トークンをブラックリストに追加できる"""
        token = "test.token.here"
        AuthService.blacklist_token(token)

        assert AuthService.is_token_blacklisted(token) is True

    def test_is_token_not_blacklisted(self):
        """ブラックリストに登録されていないトークンの確認"""
        token = "test.token.here"

        assert AuthService.is_token_blacklisted(token) is False

    def test_verify_blacklisted_token_fails(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """ブラックリストに登録されたトークンは検証に失敗する"""
        token = AuthService.create_access_token(test_user.id)

        # トークンをブラックリストに追加
        AuthService.blacklist_token(token)

        # 検証が失敗する
        verified_user = auth_service.verify_token(token)
        assert verified_user is None

    def test_refresh_blacklisted_token_fails(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """ブラックリストに登録されたリフレッシュトークンは使用できない"""
        refresh_token = AuthService.create_refresh_token(test_user.id)

        # トークンをブラックリストに追加
        AuthService.blacklist_token(refresh_token)

        # リフレッシュが失敗する
        new_access_token = auth_service.refresh_access_token(refresh_token)
        assert new_access_token is None

    def test_logout_user(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """ログアウト処理でトークンが無効化される"""
        token = AuthService.create_access_token(test_user.id)

        # ログアウト
        result = auth_service.logout_user(token)
        assert result is True

        # トークンがブラックリストに登録されている
        assert AuthService.is_token_blacklisted(token) is True

        # トークン検証が失敗する
        verified_user = auth_service.verify_token(token)
        assert verified_user is None


class TestEdgeCases:
    """エッジケースのテスト"""

    def setup_method(self):
        """各テストメソッド前にブラックリストをクリア"""
        _token_blacklist.clear()

    def test_create_token_with_zero_user_id(self):
        """ユーザーID=0でもトークン生成は可能"""
        token = AuthService.create_access_token(0)
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["sub"] == "0"

    def test_create_token_with_negative_user_id(self):
        """負のユーザーIDでもトークン生成は可能（検証時に拒否される）"""
        token = AuthService.create_access_token(-1)
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        assert payload["sub"] == "-1"

    def test_authenticate_user_with_special_characters(
        self, db_session: Session, auth_service: AuthService
    ):
        """特殊文字を含むユーザー名での認証"""
        # 特殊文字を含むユーザーを作成
        special_user = User(
            username="user@test.com",
            email="special@example.com",
            hashed_password=AuthService.hash_password("password123"),
        )
        db_session.add(special_user)
        db_session.commit()

        # 認証が成功する
        authenticated = auth_service.authenticate_user(
            "user@test.com", "password123"
        )
        assert authenticated is not None
        assert authenticated.username == "user@test.com"

    def test_multiple_tokens_for_same_user(
        self, db_session: Session, auth_service: AuthService, test_user: User
    ):
        """同じユーザーに対して複数のトークンを発行できる"""
        token1 = AuthService.create_access_token(test_user.id)
        # 少し時間を空けて異なるトークンを生成
        time.sleep(1)
        token2 = AuthService.create_access_token(test_user.id)

        # 両方とも有効
        assert token1 != token2
        verified1 = auth_service.verify_token(token1)
        verified2 = auth_service.verify_token(token2)
        assert verified1 is not None
        assert verified2 is not None

        # 片方をブラックリストに追加
        AuthService.blacklist_token(token1)

        # token1は無効、token2は有効
        verified1 = auth_service.verify_token(token1)
        verified2 = auth_service.verify_token(token2)
        assert verified1 is None
        assert verified2 is not None
