"""
ログサービス

構造化JSONログ（コンソール出力 + ファイル出力）を提供する。

出力方式:
- コンソール（stdout）: ECS Fargate が標準出力を CloudWatch Logs へ自動転送
- ファイル（RotatingFileHandler）: ローカル確認用、10MB × 5世代でローテーション

ログ形式（JSON）:
    {
        "timestamp": "2024-01-01T00:00:00+00:00",
        "level": "ERROR",
        "logger": "subscription_manager",
        "message": "エラーメッセージ",
        "error_type": "ValueError",   # log_error のみ
        "context": {...},             # log_error のみ
        "user_id": 1,                 # log_user_action のみ
        "action": "subscription_created",  # log_user_action のみ
        "details": {...}              # log_user_action のみ
    }
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    構造化JSONログフォーマッター。

    各ログレコードを JSON 文字列に変換する。
    extra={"extra_fields": {...}} で渡した値をトップレベルにマージする。
    """

    def format(self, record: logging.LogRecord) -> str:
        """LogRecord を JSON 文字列にフォーマットする"""
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # extra_fields がある場合はトップレベルにマージ
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        return json.dumps(log_data, ensure_ascii=False)


class LoggingService:
    """
    構造化JSONログサービスクラス。

    Python 標準の logging モジュールをラップし、
    アプリケーション全体で一貫したログ出力を提供する。
    同名ロガーへの重複ハンドラー追加を防ぐため、
    最初の初期化時のみハンドラーをセットアップする。
    """

    def __init__(
        self,
        logger_name: str = "subscription_manager",
        log_file: str | None = "logs/app.log",
    ) -> None:
        """
        引数:
            logger_name: ロガー名（デフォルト: "subscription_manager"）
            log_file: ログファイルパス。None の場合はファイル出力なし
        """
        self.logger = logging.getLogger(logger_name)
        # 同名ロガーへの重複ハンドラー追加を防ぐ
        if not self.logger.handlers:
            self._setup_handlers(log_file)

    def _setup_handlers(self, log_file: str | None) -> None:
        """
        ログハンドラーをセットアップする。

        コンソールハンドラー（stdout）は常に追加する。
        ファイルハンドラーは log_file が指定された場合のみ追加する。
        """
        self.logger.setLevel(logging.INFO)
        formatter = JsonFormatter()

        # コンソールハンドラー（stdout）
        # ECS Fargate では標準出力が CloudWatch Logs へ自動転送される
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # ファイルハンドラー（10MB × 5世代ローテーション）
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log_error(self, error: Exception, context: dict[str, Any]) -> None:
        """
        エラーログを ERROR レベルで出力する。

        引数:
            error: 発生した例外
            context: エラーの文脈情報（例: {"user_id": 1, "endpoint": "/subscriptions"}）
        """
        self.logger.error(
            str(error),
            extra={
                "extra_fields": {
                    "error_type": type(error).__name__,
                    "context": context,
                }
            },
        )

    def log_user_action(
        self, user_id: int, action: str, details: dict[str, Any]
    ) -> None:
        """
        ユーザーアクションログを INFO レベルで出力する。

        引数:
            user_id: アクションを実行したユーザーID
            action: アクション名（例: "subscription_created", "login"）
            details: アクションの詳細情報
        """
        self.logger.info(
            action,
            extra={
                "extra_fields": {
                    "user_id": user_id,
                    "action": action,
                    "details": details,
                }
            },
        )
