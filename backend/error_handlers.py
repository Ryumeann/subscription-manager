"""
グローバルエラーハンドラー

FastAPI アプリケーション全体で発生するエラーを統一フォーマットで返す。
register_error_handlers(app) を main.py で呼び出して登録する。

対応するエラー:
- HTTPException: 404/401/403 などの HTTP エラー
- RequestValidationError: リクエストのバリデーションエラー（422）
- Exception: 予期しない内部サーバーエラー（500）

レスポンス形式: ErrorResponse スキーマ（日本語メッセージ + UUID request_id）
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.schemas.error import ErrorResponse


def _make_error_response(
    error_code: str,
    message: str,
    details: dict | None = None,
) -> dict:
    """
    ErrorResponse の dict を生成するヘルパー。

    model_dump(mode="json") で datetime を ISO 文字列に変換する。
    """
    return ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        timestamp=datetime.now(timezone.utc),
        request_id=str(uuid4()),
    ).model_dump(mode="json")


async def _http_exception_handler(
    _request: Request, exc: HTTPException
) -> JSONResponse:
    """
    HTTPException ハンドラー。

    各ルーターで raise HTTPException(..., detail="日本語メッセージ") した場合に
    ErrorResponse 形式で返す。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=_make_error_response(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        ),
    )


async def _validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    リクエストバリデーションエラーハンドラー（422）。

    Pydantic のバリデーション失敗時に日本語メッセージと
    エラー詳細を返す。

    注: exc.errors() は ctx フィールドに元の ValueError オブジェクト等の
    JSONシリアライズできない値を含むことがあるため、ctx を除外したコピーを返す。
    """
    # ctx と input フィールドは JSON シリアライズできない値を含む可能性があるため除外
    sanitized_errors = [
        {k: v for k, v in err.items() if k not in ("ctx", "input")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_make_error_response(
            error_code="VALIDATION_ERROR",
            message="入力データが正しくありません",
            details={"errors": sanitized_errors},
        ),
    )


async def _generic_exception_handler(
    _request: Request, _exc: Exception
) -> JSONResponse:
    """
    予期しない例外ハンドラー（500）。

    内部エラーの詳細はレスポンスに含めず、ユーザーフレンドリーな
    日本語メッセージのみ返す。
    """
    return JSONResponse(
        status_code=500,
        content=_make_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            message="サーバー内部エラーが発生しました。しばらく経ってから再試行してください",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    FastAPI アプリに全エラーハンドラーを登録する。

    main.py の app 生成直後に呼び出すこと。
    """
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_exception_handler)
