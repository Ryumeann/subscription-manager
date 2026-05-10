"""
FastAPIアプリケーションのエントリポイント

起動コマンド: poetry run uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.error_handlers import register_error_handlers
from backend.middleware.security import CSRFProtectionMiddleware, SecurityHeadersMiddleware
from backend.routers import auth, dashboard, subscriptions

settings = get_settings()

# 開発環境でのみ API ドキュメント（Swagger UI / ReDoc / OpenAPI スキーマ）を公開する
# 本番環境では攻撃面を減らすため非公開（404）にする
_is_dev = settings.app_env == "development"

app = FastAPI(
    title="サブスクリプション管理API",
    description="サブスクリプション契約を一元管理するためのREST API",
    version="0.1.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

# グローバルエラーハンドラー登録（ルーター登録前に行う）
register_error_handlers(app)

# CORS設定: 許可オリジンからのクロスオリジンリクエストを制御
# Streamlitフロントエンド（localhost:8501）からのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# CSRF保護: 状態変更リクエストのOriginヘッダーを検証
app.add_middleware(CSRFProtectionMiddleware, allowed_origins=settings.cors_allowed_origins)

# セキュリティヘッダー: XSS・クリックジャッキング防止ヘッダーを全レスポンスに付与
app.add_middleware(SecurityHeadersMiddleware, app_env=settings.app_env)

# ルーター登録
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(dashboard.router)


@app.get("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}
