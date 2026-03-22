"""
ダッシュボードAPIルーター

ダッシュボード表示に必要なデータを提供するエンドポイント。
全エンドポイントはJWT認証が必要。

エンドポイント:
- GET /dashboard          - ダッシュボード全データ取得
- GET /dashboard/categories - カテゴリ別月額支出集計
- GET /dashboard/trends   - 過去12ヶ月の支出推移
- GET /dashboard/renewals - 7日以内の更新予定一覧
"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.dashboard import DashboardData
from backend.schemas.subscription import MonthlySpending, SubscriptionResponse
from backend.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["ダッシュボード"])


@router.get("", response_model=DashboardData)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardData:
    """
    ダッシュボード全データを取得する。

    月間総支出、アクティブ件数、カテゴリ別内訳、
    更新予定（7日以内）、12ヶ月支出推移をまとめて返す。
    """
    service = DashboardService(db)
    return service.get_dashboard_data(current_user.id)


@router.get("/categories", response_model=dict[str, Decimal])
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Decimal]:
    """
    カテゴリ別月額支出の集計を取得する。

    例: {"動画配信": 1980.00, "音楽": 980.00}
    """
    service = DashboardService(db)
    return service.get_category_breakdown(current_user.id)


@router.get("/trends", response_model=list[MonthlySpending])
def get_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MonthlySpending]:
    """
    過去12ヶ月の月別支出推移を取得する。

    古い月から昇順（12ヶ月前 → 今月）で返す。
    """
    service = DashboardService(db)
    return service.get_spending_trends(current_user.id)


@router.get("/renewals", response_model=list[SubscriptionResponse])
def get_renewals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SubscriptionResponse]:
    """
    7日以内に更新日が来るサブスクリプション一覧を取得する。

    next_renewal_date の昇順で返す。今日が更新日のものも含む。
    """
    service = DashboardService(db)
    subscriptions = service.get_upcoming_renewals(current_user.id)
    return [SubscriptionResponse.model_validate(s) for s in subscriptions]
