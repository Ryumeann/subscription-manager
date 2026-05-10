"""
認証ルーター

新規登録、ログイン、ログアウト、トークン更新のAPIエンドポイントを提供する。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["認証"])

security = HTTPBearer(auto_error=False)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    新規ユーザー登録

    ユーザー名・パスワードを受け取り、新規アカウントを作成する。
    登録成功時は自動ログイン扱いとし、トークンペアを返す。

    エラー:
    - 409 Conflict: ユーザー名が既に使われている
    - 422 Unprocessable Entity: 入力値のバリデーションエラー（Pydantic自動）
    """
    auth_service = AuthService(db)

    try:
        user = auth_service.create_user(
            username=request.username,
            password=request.password,
        )
    except AuthService.DuplicateUserError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    # 登録成功時はそのままトークンを発行（自動ログイン扱い）
    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    ユーザーログイン

    ユーザー名とパスワードで認証し、アクセストークンとリフレッシュトークンを返す。
    """
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(request.username, request.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    ユーザーログアウト

    現在のアクセストークンをブラックリストに追加して無効化する。
    """
    auth_service = AuthService(db)
    auth_service.logout_user(credentials.credentials)
    return {"message": "ログアウトしました"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: RefreshRequest, db: Session = Depends(get_db)
) -> TokenResponse:
    """
    トークン更新

    リフレッシュトークンを検証し、新しいアクセストークンとリフレッシュトークンを返す。
    """
    auth_service = AuthService(db)
    new_access_token = auth_service.refresh_access_token(request.refresh_token)

    if new_access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なリフレッシュトークンまたは期限切れです",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # リフレッシュ時に新しいトークンペアを発行（トークンローテーション）
    # 古いリフレッシュトークンをブラックリストに追加
    auth_service.blacklist_token(request.refresh_token)

    # リフレッシュトークンからuser_idを取得して新しいリフレッシュトークンを生成
    from jose import jwt
    from backend.config import get_settings

    settings = get_settings()
    payload = jwt.decode(
        request.refresh_token, settings.secret_key, algorithms=[settings.algorithm]
    )
    user_id = int(payload["sub"])
    new_refresh_token = auth_service.create_refresh_token(user_id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )
