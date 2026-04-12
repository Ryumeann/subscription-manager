"""
ログサービスの単体テスト（タスク8.2）

テスト対象:
- JsonFormatter: ログレコードの JSON フォーマット
- LoggingService.log_error: エラーログ出力
- LoggingService.log_user_action: ユーザーアクションログ出力
"""

import json
import logging
from uuid import uuid4

import pytest

from backend.services.logging_service import JsonFormatter, LoggingService


def _unique_logger_name() -> str:
    """テストごとにユニークなロガー名を生成してハンドラーの汚染を防ぐ"""
    return f"test_{uuid4().hex}"


def _make_log_record(
    level: int = logging.INFO,
    msg: str = "テストメッセージ",
    name: str = "test",
    extra_fields: dict | None = None,
) -> logging.LogRecord:
    """テスト用 LogRecord 生成ヘルパー"""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if extra_fields is not None:
        record.extra_fields = extra_fields
    return record


# ==============================================================================
# JsonFormatter のテスト
# ==============================================================================


class TestJsonFormatter:
    """JsonFormatter のユニットテスト"""

    def test_有効なJSONを出力する(self):
        """format() の戻り値が JSON としてパースできる"""
        formatter = JsonFormatter()
        record = _make_log_record()

        output = formatter.format(record)
        data = json.loads(output)  # パースできること

        assert isinstance(data, dict)

    def test_必須フィールドが含まれる(self):
        """timestamp, level, logger, message が出力に含まれる"""
        formatter = JsonFormatter()
        record = _make_log_record(msg="テストメッセージ")

        data = json.loads(formatter.format(record))

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "テストメッセージ"

    def test_ERRORレベルが正しく出力される(self):
        """ERROR レベルのレコードは level=ERROR で出力される"""
        formatter = JsonFormatter()
        record = _make_log_record(level=logging.ERROR, msg="エラー発生")

        data = json.loads(formatter.format(record))

        assert data["level"] == "ERROR"

    def test_extra_fieldsがトップレベルにマージされる(self):
        """extra_fields の内容が JSON のトップレベルに展開される"""
        formatter = JsonFormatter()
        extra = {"error_type": "ValueError", "context": {"key": "value"}}
        record = _make_log_record(extra_fields=extra)

        data = json.loads(formatter.format(record))

        assert data["error_type"] == "ValueError"
        assert data["context"] == {"key": "value"}

    def test_extra_fieldsなしでもエラーにならない(self):
        """extra_fields が未設定のレコードも正常にフォーマットされる"""
        formatter = JsonFormatter()
        record = _make_log_record()

        output = formatter.format(record)

        assert json.loads(output) is not None

    def test_日本語文字列が正しくエンコードされる(self):
        """日本語を含むメッセージが文字化けせず出力される"""
        formatter = JsonFormatter()
        record = _make_log_record(msg="日本語メッセージテスト")

        data = json.loads(formatter.format(record))

        assert data["message"] == "日本語メッセージテスト"

    def test_timestampがISO形式である(self):
        """timestamp フィールドが ISO 8601 形式の文字列である"""
        from datetime import datetime

        formatter = JsonFormatter()
        record = _make_log_record()

        data = json.loads(formatter.format(record))

        # ISO 形式としてパースできること
        dt = datetime.fromisoformat(data["timestamp"])
        assert dt.tzinfo is not None  # タイムゾーン情報を含む


# ==============================================================================
# LoggingService.log_error のテスト
# ==============================================================================


class TestLogError:
    """log_error のテスト"""

    def test_ERRORレベルでログ出力される(self, caplog):
        """log_error は ERROR レベルでログを出力する"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.ERROR):
            service.log_error(ValueError("テストエラー"), {})

        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(error_records) == 1

    def test_error_typeが記録される(self, caplog):
        """error_type フィールドに例外クラス名が記録される"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.ERROR):
            service.log_error(ValueError("テストエラー"), {})

        record = next(r for r in caplog.records if r.levelname == "ERROR")
        assert record.extra_fields["error_type"] == "ValueError"

    def test_contextが記録される(self, caplog):
        """context 辞書の内容が記録される"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)
        context = {"user_id": 1, "endpoint": "/subscriptions"}

        with caplog.at_level(logging.ERROR):
            service.log_error(RuntimeError("DB接続失敗"), context)

        record = next(r for r in caplog.records if r.levelname == "ERROR")
        assert record.extra_fields["context"] == context

    def test_messageにエラー文字列が含まれる(self, caplog):
        """ログメッセージにエラーの str 表現が含まれる"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.ERROR):
            service.log_error(ValueError("エラーの詳細メッセージ"), {})

        record = next(r for r in caplog.records if r.levelname == "ERROR")
        assert "エラーの詳細メッセージ" in record.message

    def test_JSONとして出力可能(self, caplog):
        """log_error の出力が JsonFormatter で有効な JSON になる"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.ERROR):
            service.log_error(TypeError("型エラー"), {"key": "val"})

        record = next(r for r in caplog.records if r.levelname == "ERROR")
        formatter = JsonFormatter()
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert data["error_type"] == "TypeError"


# ==============================================================================
# LoggingService.log_user_action のテスト
# ==============================================================================


class TestLogUserAction:
    """log_user_action のテスト"""

    def test_INFOレベルでログ出力される(self, caplog):
        """log_user_action は INFO レベルでログを出力する"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.INFO):
            service.log_user_action(1, "subscription_created", {})

        info_records = [r for r in caplog.records if r.levelname == "INFO"]
        assert len(info_records) == 1

    def test_user_idが記録される(self, caplog):
        """user_id フィールドに指定したユーザーIDが記録される"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.INFO):
            service.log_user_action(42, "login", {})

        record = next(r for r in caplog.records if r.levelname == "INFO")
        assert record.extra_fields["user_id"] == 42

    def test_actionが記録される(self, caplog):
        """action フィールドにアクション名が記録される"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.INFO):
            service.log_user_action(1, "subscription_deleted", {})

        record = next(r for r in caplog.records if r.levelname == "INFO")
        assert record.extra_fields["action"] == "subscription_deleted"

    def test_detailsが記録される(self, caplog):
        """details 辞書の内容が記録される"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)
        details = {"service_name": "Netflix", "monthly_fee": 1980}

        with caplog.at_level(logging.INFO):
            service.log_user_action(1, "subscription_created", details)

        record = next(r for r in caplog.records if r.levelname == "INFO")
        assert record.extra_fields["details"] == details

    def test_JSONとして出力可能(self, caplog):
        """log_user_action の出力が JsonFormatter で有効な JSON になる"""
        service = LoggingService(logger_name=_unique_logger_name(), log_file=None)

        with caplog.at_level(logging.INFO):
            service.log_user_action(5, "logout", {"session": "abc"})

        record = next(r for r in caplog.records if r.levelname == "INFO")
        formatter = JsonFormatter()
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["user_id"] == 5
        assert data["action"] == "logout"
