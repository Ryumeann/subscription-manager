"""
認証サービス

JWTトークンのライフサイクル管理、パスワードハッシュ化、
トークンブラックリストを担当する。

- パスワードハッシュ: bcrypt（passlib経由）
- JWT: python-jose（HS256アルゴリズム）
- トークンブラックリスト: ログアウト時にサーバー側でトークンを無効化
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.user import User

settings = get_settings()

# bcryptを使ったパスワードハッシュ化コンテキスト
# schemes=["bcrypt"]: ハッシュアルゴリズムにbcryptを使用
# deprecated="auto": 古いスキームは自動的に非推奨扱い
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# トークンブラックリスト（ログアウト済みトークンを保持）
# 注意: インメモリのため、サーバー再起動でリセットされる
# 本番環境ではRedisやDBテーブルでの管理を推奨
_token_blacklist: set[str] = set()


class AuthService:
    """認証サービスクラス"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- パスワード関連 ---

    @staticmethod
    def hash_password(password: str) -> str:
        """パスワードをbcryptでハッシュ化する"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """平文パスワードとハッシュを照合する"""
        return pwd_context.verify(plain_password, hashed_password)

    # --- ユーザー登録 ---

    class DuplicateUserError(Exception):
        """ユーザー名が既に登録されている場合に送出する例外"""

        def __init__(self, field: str, message: str) -> None:
            self.field = field  # 現状は "username" のみ
            super().__init__(message)

    def create_user(self, username: str, password: str) -> User:
        """
        新規ユーザーをDBに作成する。

        - パスワードはbcryptでハッシュ化して保存
        - username の一意性を事前チェックし、重複時は DuplicateUserError を送出
        """
        existing_username = (
            self.db.query(User).filter(User.username == username).first()
        )
        if existing_username is not None:
            raise self.DuplicateUserError(
                "username", "このユーザー名は既に使われています"
            )

        user = User(
            username=username,
            hashed_password=self.hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # --- ユーザー認証 ---

    def authenticate_user(
        self, username: str, password: str
    ) -> Optional[User]:
        """
        ユーザー名とパスワードで認証する。

        認証成功時はUserオブジェクトを返し、失敗時はNoneを返す。
        """
        user = self.db.query(User).filter(User.username == username).first()
        if user is None:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    # --- トークン生成 ---

    @staticmethod
    def create_access_token(
        user_id: int,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        アクセストークン（JWT）を生成する。

        ペイロード:
        - sub: ユーザーID（文字列）
        - type: "access"
        - exp: 有効期限（デフォルト24時間）
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=settings.access_token_expire_hours)
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": expire,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    @staticmethod
    def create_refresh_token(
        user_id: int,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        リフレッシュトークン（JWT）を生成する。

        ペイロード:
        - sub: ユーザーID（文字列）
        - type: "refresh"
        - exp: 有効期限（デフォルト30日）
        """
        if expires_delta is None:
            expires_delta = timedelta(days=settings.refresh_token_expire_days)
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    # --- トークン検証 ---

    def verify_token(self, token: str) -> Optional[User]:
        """
        アクセストークンを検証し、対応するユーザーを返す。

        以下の場合はNoneを返す:
        - トークンが無効（署名不正、フォーマット不正）
        - トークンが期限切れ
        - トークンがブラックリストに登録済み
        - トークンタイプが "access" でない
        - 対応するユーザーが存在しない
        """
        if self.is_token_blacklisted(token):
            return None
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[settings.algorithm]
            )
        except JWTError:
            return None

        if payload.get("type") != "access":
            return None

        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return None

        return self.db.query(User).filter(User.id == user_id).first()

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        リフレッシュトークンを検証し、新しいアクセストークンを返す。

        リフレッシュトークンが無効な場合はNoneを返す。
        """
        if self.is_token_blacklisted(refresh_token):
            return None
        try:
            payload = jwt.decode(
                refresh_token, settings.secret_key, algorithms=[settings.algorithm]
            )
        except JWTError:
            return None

        if payload.get("type") != "refresh":
            return None

        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return None

        # ユーザーの存在確認
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None

        return self.create_access_token(user_id)

    # --- トークンブラックリスト ---

    @staticmethod
    def blacklist_token(token: str) -> None:
        """トークンをブラックリストに追加する（ログアウト処理）"""
        _token_blacklist.add(token)

    @staticmethod
    def is_token_blacklisted(token: str) -> bool:
        """トークンがブラックリストに登録されているか確認する"""
        return token in _token_blacklist

    def logout_user(self, token: str) -> bool:
        """
        ユーザーをログアウトする。

        トークンをブラックリストに追加して無効化する。
        """
        self.blacklist_token(token)
        return True
