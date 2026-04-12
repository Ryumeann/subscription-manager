"""
エラーレスポンス用Pydanticスキーマ

design.md のエラーレスポンス形式に準拠。
全APIエラーはこのスキーマで統一されたフォーマットで返す。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """APIエラーレスポンススキーマ"""

    error_code: str
    """エラー種別コード（例: HTTP_404, VALIDATION_ERROR, INTERNAL_SERVER_ERROR）"""
    message: str
    """日本語のエラーメッセージ"""
    details: Optional[dict[str, Any]] = None
    """追加情報（バリデーションエラーの詳細など）"""
    timestamp: datetime
    """エラー発生日時（UTC）"""
    request_id: str
    """リクエスト識別子（デバッグ用UUID）"""
