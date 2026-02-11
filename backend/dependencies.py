"""
FastAPI依存性注入モジュール

認証済みユーザーの取得など、エンドポイント共通の依存性を定義する。
FastAPIのDepends()で各エンドポイントに注入して使用する。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.services.auth_service import AuthService

# HTTPBearer: Authorizationヘッダーから "Bearer <token>" を抽出するスキーム
# auto_error=False: トークン未送信時に自動で403を返さず、Noneを返す（自前で401を返すため）
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    認証済みユーザーを取得する依存性注入関数。

    Authorizationヘッダーからアクセストークンを取得し、
    検証に成功した場合はUserオブジェクトを返す。
    失敗した場合は401エラーを返す。

    使用例:
        @app.get("/protected")
        def protected_route(user: User = Depends(get_current_user)):
            return {"user": user.username}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(db)
    user = auth_service.verify_token(credentials.credentials)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンまたは期限切れです",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
