"""
セキュリティミドルウェアモジュール

XSS防止・クリックジャッキング防止などのセキュリティヘッダーを付与するミドルウェアと、
CSRFトークン検証ミドルウェアを提供する。

【SQLインジェクション防止について】
SQLAlchemy ORMを使用したパラメータバインディングにより、
SQLインジェクション攻撃は構造的に防止されている。
（すべてのDB操作は backend/services/ 配下のサービス層で ORM 経由で行う）
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    XSS・クリックジャッキング防止のセキュリティヘッダーミドルウェア

    すべてのレスポンスに以下のヘッダーを付与する:
    - X-Content-Type-Options: MIMEスニッフィング防止（XSS対策）
    - X-Frame-Options: クリックジャッキング防止
    - X-XSS-Protection: ブラウザ組み込みXSSフィルター有効化（旧ブラウザ向け）
    - Content-Security-Policy: スクリプト読み込み元制限（XSS対策）
    - Strict-Transport-Security: HTTPS強制（本番環境向け）
    - Referrer-Policy: リファラー情報の送信制限
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # MIMEスニッフィング防止: ブラウザがContent-Typeを無視して内容を推測するのを禁止
        response.headers["X-Content-Type-Options"] = "nosniff"

        # クリックジャッキング防止: iframeへの埋め込みを禁止
        response.headers["X-Frame-Options"] = "DENY"

        # XSSフィルター: 旧来のブラウザ向けXSS保護を有効化
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # コンテンツセキュリティポリシー: APIサーバーなのでデフォルトを全拒否
        response.headers["Content-Security-Policy"] = "default-src 'none'"

        # Referrer-Policy: センシティブなURLをリファラーに含めない
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS: HTTPSのみ許可（Strict-Transport-Security）
        # max-age=31536000 = 1年間HTTPSを強制
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRFオリジン検証ミドルウェア

    【このミドルウェアが必要な理由】
    このAPIはJWT認証にAuthorizationヘッダー（Bearer token）を使用しているため、
    ブラウザが自動送信するCookie認証のようなCSRF攻撃は成立しない。
    しかし、将来的にCookie認証に変更する可能性や、
    悪意あるサイトからのクロスオリジンリクエストを明示的に拒否するため、
    状態変更リクエスト（POST/PUT/DELETE）に対してOriginヘッダーを検証する。

    検証ロジック:
    - GET/HEAD/OPTIONS は読み取り専用のため検証をスキップ
    - それ以外のメソッドはOriginヘッダーが許可リストに含まれるか検証
    - Originヘッダーがない場合は内部呼び出し（curl等）とみなし許可
    """

    # 状態を変更するHTTPメソッド
    _STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self._STATE_CHANGING_METHODS:
            origin = request.headers.get("origin")

            # Originヘッダーが存在する場合のみ検証（curl等の直接呼び出しは許可）
            if origin is not None and origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error_code": "CSRF_FORBIDDEN",
                        "message": "許可されていないオリジンからのリクエストです",
                    },
                )

        return await call_next(request)
