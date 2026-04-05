"""
Pydanticスキーマの入力検証テスト

リクエストスキーマのバリデーションルールが正しく機能することを確認する。
金額、カテゴリ、日付、テキスト入力の検証をテストする。
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.models.subscription_category import SubscriptionCategory
from backend.schemas.auth import LoginRequest, RefreshRequest, TokenData, TokenResponse
from backend.schemas.subscription import (
    MonthlySpending,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)


class TestAuthSchemas:
    """認証スキーマのバリデーションテスト"""

    def test_login_request_valid(self):
        """正常なログインリクエスト"""
        data = {"username": "testuser", "password": "testpass123"}
        login_req = LoginRequest(**data)

        assert login_req.username == "testuser"
        assert login_req.password == "testpass123"

    def test_login_request_empty_username(self):
        """空のユーザー名（バリデーションエラー）"""
        data = {"username": "", "password": "testpass123"}

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_login_request_empty_password(self):
        """空のパスワード（バリデーションエラー）"""
        data = {"username": "testuser", "password": ""}

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

    def test_login_request_missing_fields(self):
        """必須フィールド不足（バリデーションエラー）"""
        with pytest.raises(ValidationError):
            LoginRequest()

    def test_token_response_valid(self):
        """正常なトークンレスポンス"""
        data = {
            "access_token": "access.token.here",
            "refresh_token": "refresh.token.here",
        }
        token_resp = TokenResponse(**data)

        assert token_resp.access_token == "access.token.here"
        assert token_resp.refresh_token == "refresh.token.here"
        assert token_resp.token_type == "bearer"

    def test_refresh_request_valid(self):
        """正常なトークン更新リクエスト"""
        data = {"refresh_token": "refresh.token.here"}
        refresh_req = RefreshRequest(**data)

        assert refresh_req.refresh_token == "refresh.token.here"

    def test_token_data_valid(self):
        """正常なトークンデータ"""
        data = {"user_id": 1, "token_type": "access"}
        token_data = TokenData(**data)

        assert token_data.user_id == 1
        assert token_data.token_type == "access"


class TestSubscriptionCreateSchema:
    """SubscriptionCreateスキーマのバリデーションテスト"""

    def test_subscription_create_valid(self):
        """正常なサブスクリプション作成リクエスト"""
        data = {
            "service_name": "Netflix",
            "monthly_fee": Decimal("1980.00"),
            "category": SubscriptionCategory.VIDEO_STREAMING,
            "start_date": date(2024, 1, 1),
            "next_renewal_date": date(2024, 2, 1),
            "memo": "プレミアムプラン",
        }
        sub_create = SubscriptionCreate(**data)

        assert sub_create.service_name == "Netflix"
        assert sub_create.monthly_fee == Decimal("1980.00")
        assert sub_create.category == SubscriptionCategory.VIDEO_STREAMING
        assert sub_create.start_date == date(2024, 1, 1)
        assert sub_create.next_renewal_date == date(2024, 2, 1)
        assert sub_create.memo == "プレミアムプラン"

    def test_subscription_create_without_optional_fields(self):
        """オプションフィールドなしのサブスクリプション作成"""
        data = {
            "service_name": "Spotify",
            "monthly_fee": Decimal("980.00"),
            "category": SubscriptionCategory.MUSIC,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)

        assert sub_create.service_name == "Spotify"
        assert sub_create.next_renewal_date is None
        assert sub_create.memo is None

    # --- 金額検証テスト ---

    def test_monthly_fee_positive_number(self):
        """金額は正の数値であることを確認"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("0.01"),  # 最小値
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.monthly_fee == Decimal("0.01")

    def test_monthly_fee_zero_invalid(self):
        """金額が0はバリデーションエラー"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("0.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("monthly_fee",) for error in errors)

    def test_monthly_fee_negative_invalid(self):
        """負の金額はバリデーションエラー"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("-100.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("monthly_fee",) for error in errors)

    def test_monthly_fee_decimal_precision(self):
        """小数点以下2桁の金額フォーマット"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1234.56"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.monthly_fee == Decimal("1234.56")

    def test_monthly_fee_from_string(self):
        """文字列からDecimalへの変換"""
        data = {
            "service_name": "Test",
            "monthly_fee": "1980.00",  # 文字列
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.monthly_fee == Decimal("1980.00")
        assert isinstance(sub_create.monthly_fee, Decimal)

    # --- カテゴリ制限テスト ---

    def test_category_video_streaming(self):
        """カテゴリ: VIDEO_STREAMING"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.VIDEO_STREAMING,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.VIDEO_STREAMING

    def test_category_music(self):
        """カテゴリ: MUSIC"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.MUSIC,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.MUSIC

    def test_category_gaming(self):
        """カテゴリ: GAMING"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.GAMING,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.GAMING

    def test_category_cloud(self):
        """カテゴリ: CLOUD"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.CLOUD,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.CLOUD

    def test_category_tool(self):
        """カテゴリ: TOOL"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.TOOL,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.TOOL

    def test_category_media(self):
        """カテゴリ: MEDIA"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.MEDIA,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.MEDIA

    def test_category_other(self):
        """カテゴリ: OTHER"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.OTHER

    def test_category_invalid_string(self):
        """無効なカテゴリ文字列（バリデーションエラー）"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": "INVALID_CATEGORY",
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("category",) for error in errors)

    def test_category_from_value_string(self):
        """カテゴリの値文字列から列挙型への変換"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": "動画配信",  # 値文字列
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.category == SubscriptionCategory.VIDEO_STREAMING

    # --- 日付検証テスト ---

    def test_date_format_valid(self):
        """正しい日付フォーマット"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
            "next_renewal_date": date(2024, 2, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.start_date == date(2024, 1, 1)
        assert sub_create.next_renewal_date == date(2024, 2, 1)

    def test_date_from_string(self):
        """文字列から日付への変換"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": "2024-01-01",  # 文字列
            "next_renewal_date": "2024-02-01",
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.start_date == date(2024, 1, 1)
        assert sub_create.next_renewal_date == date(2024, 2, 1)

    def test_date_invalid_format(self):
        """無効な日付フォーマット（バリデーションエラー）"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": "2024/01/01",  # 無効なフォーマット
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("start_date",) for error in errors)

    # --- テキスト入力検証テスト ---

    def test_service_name_valid_length(self):
        """サービス名の有効な長さ"""
        data = {
            "service_name": "A" * 100,  # 最大長
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }
        sub_create = SubscriptionCreate(**data)
        assert len(sub_create.service_name) == 100

    def test_service_name_empty_string(self):
        """空のサービス名（バリデーションエラー）"""
        data = {
            "service_name": "",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("service_name",) for error in errors)

    def test_service_name_too_long(self):
        """サービス名が長すぎる（バリデーションエラー）"""
        data = {
            "service_name": "A" * 101,  # 101文字
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("service_name",) for error in errors)

    def test_memo_valid_length(self):
        """メモの有効な長さ"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
            "memo": "A" * 500,  # 最大長
        }
        sub_create = SubscriptionCreate(**data)
        assert len(sub_create.memo) == 500

    def test_memo_too_long(self):
        """メモが長すぎる（バリデーションエラー）"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
            "memo": "A" * 501,  # 501文字
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("memo",) for error in errors)

    def test_memo_empty_string_allowed(self):
        """空文字列のメモは許可される"""
        data = {
            "service_name": "Test",
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
            "memo": "",
        }
        sub_create = SubscriptionCreate(**data)
        assert sub_create.memo == ""

    # --- 必須フィールドのテスト ---

    def test_missing_required_field_service_name(self):
        """必須フィールド不足: service_name"""
        data = {
            "monthly_fee": Decimal("1000.00"),
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("service_name",) for error in errors)

    def test_missing_required_field_monthly_fee(self):
        """必須フィールド不足: monthly_fee"""
        data = {
            "service_name": "Test",
            "category": SubscriptionCategory.OTHER,
            "start_date": date(2024, 1, 1),
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("monthly_fee",) for error in errors)


class TestSubscriptionUpdateSchema:
    """SubscriptionUpdateスキーマのバリデーションテスト"""

    def test_subscription_update_all_fields(self):
        """全フィールドを更新"""
        data = {
            "service_name": "Updated Service",
            "monthly_fee": Decimal("2000.00"),
            "category": SubscriptionCategory.MUSIC,
            "start_date": date(2024, 2, 1),
            "next_renewal_date": date(2024, 3, 1),
            "memo": "更新後",
        }
        sub_update = SubscriptionUpdate(**data)

        assert sub_update.service_name == "Updated Service"
        assert sub_update.monthly_fee == Decimal("2000.00")
        assert sub_update.category == SubscriptionCategory.MUSIC

    def test_subscription_update_partial_fields(self):
        """一部フィールドのみ更新"""
        data = {
            "monthly_fee": Decimal("2500.00"),
        }
        sub_update = SubscriptionUpdate(**data)

        assert sub_update.monthly_fee == Decimal("2500.00")
        assert sub_update.service_name is None
        assert sub_update.category is None

    def test_subscription_update_empty_object(self):
        """フィールドなしの更新リクエスト"""
        sub_update = SubscriptionUpdate()

        assert sub_update.service_name is None
        assert sub_update.monthly_fee is None
        assert sub_update.category is None

    def test_subscription_update_validation_rules(self):
        """更新時もバリデーションルールが適用される"""
        # 負の金額はエラー
        with pytest.raises(ValidationError):
            SubscriptionUpdate(monthly_fee=Decimal("-100.00"))

        # 空のサービス名はエラー
        with pytest.raises(ValidationError):
            SubscriptionUpdate(service_name="")


class TestSubscriptionResponseSchema:
    """SubscriptionResponseスキーマのテスト"""

    def test_subscription_response_from_orm(self, test_subscription):
        """ORMモデルからのレスポンススキーマ作成"""
        response = SubscriptionResponse.model_validate(test_subscription)

        assert response.id == test_subscription.id
        assert response.service_name == test_subscription.service_name
        assert response.monthly_fee == test_subscription.monthly_fee
        assert response.category == test_subscription.category
        assert response.start_date == test_subscription.start_date
        assert response.next_renewal_date == test_subscription.next_renewal_date
        assert response.memo == test_subscription.memo
        assert response.is_active == test_subscription.is_active


class TestMonthlySpendingSchema:
    """MonthlySpendingスキーマのテスト"""

    def test_monthly_spending_valid(self):
        """正常な月別支出データ"""
        data = {
            "year": 2024,
            "month": 1,
            "total_amount": Decimal("5000.00"),
        }
        spending = MonthlySpending(**data)

        assert spending.year == 2024
        assert spending.month == 1
        assert spending.total_amount == Decimal("5000.00")
