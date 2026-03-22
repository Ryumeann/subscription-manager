"""
FastAPIアプリケーションのエントリポイント

起動コマンド: poetry run uvicorn backend.main:app --reload
"""

from fastapi import FastAPI

from backend.config import get_settings
from backend.routers import auth, dashboard, subscriptions

settings = get_settings()

app = FastAPI(
    title="サブスクリプション管理API",
    description="サブスクリプション契約を一元管理するためのREST API",
    version="0.1.0",
)

# ルーター登録
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(dashboard.router)


@app.get("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}
