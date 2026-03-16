"""
サブスクリプション管理ルーター

サブスクリプションの一覧取得・新規作成・更新・削除のAPIエンドポイントを提供する。
全エンドポイントはJWT認証が必要（get_current_user依存性注入）。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from backend.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["サブスクリプション"])


@router.get("", response_model=list[SubscriptionResponse])
def get_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubscriptionResponse]:
    """
    サブスクリプション一覧取得

    ログイン中のユーザーのアクティブなサブスクリプション一覧を返す。
    """
    service = SubscriptionService(db)
    return service.get_user_subscriptions(current_user.id)


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    """
    新規サブスクリプション作成

    next_renewal_date を省略した場合は start_date の1ヶ月後が自動設定される。
    """
    service = SubscriptionService(db)
    return service.create_subscription(current_user.id, data)


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    """
    サブスクリプション更新

    送信されたフィールドのみ更新する（部分更新）。
    他のユーザーのサブスクリプションや存在しないIDを指定した場合は404を返す。
    """
    service = SubscriptionService(db)
    subscription = service.update_subscription(subscription_id, current_user.id, data)

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サブスクリプションが見つかりません",
        )

    return subscription


@router.delete("/{subscription_id}", status_code=status.HTTP_200_OK)
def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    サブスクリプション削除（論理削除）

    is_active=False に設定して論理削除する。データは保持される。
    他のユーザーのサブスクリプションや存在しないIDを指定した場合は404を返す。
    """
    service = SubscriptionService(db)
    success = service.delete_subscription(subscription_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="サブスクリプションが見つかりません",
        )

    return {"message": "サブスクリプションを削除しました"}
