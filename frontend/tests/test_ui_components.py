"""
UIコンポーネントの単体テスト

フロントエンドの定数定義・カテゴリマッピング・金額フォーマットをテストする。
"""

import sys
import os

import pytest

# frontendディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSubscriptionCategories:
    """カテゴリ定義のテスト"""

    def test_categories_list(self):
        """CATEGORIESに全7カテゴリが含まれている"""
        from pages.subscriptions import CATEGORIES

        assert len(CATEGORIES) == 7
        assert "動画配信" in CATEGORIES
        assert "音楽" in CATEGORIES
        assert "ゲーム" in CATEGORIES
        assert "クラウド" in CATEGORIES
        assert "ツール" in CATEGORIES
        assert "メディア" in CATEGORIES
        assert "その他" in CATEGORIES

    def test_categories_order(self):
        """カテゴリの並び順が正しい"""
        from pages.subscriptions import CATEGORIES

        assert CATEGORIES[0] == "動画配信"
        assert CATEGORIES[-1] == "その他"


class TestSubscriptionServices:
    """サービス一覧のテスト"""

    def test_services_list_not_empty(self):
        """サービス一覧が空でない"""
        from pages.subscriptions import SUBSCRIPTION_SERVICES

        assert len(SUBSCRIPTION_SERVICES) > 0

    def test_custom_option_exists(self):
        """「その他（直接入力）」オプションが末尾にある"""
        from pages.subscriptions import SUBSCRIPTION_SERVICES, _CUSTOM_OPTION

        assert _CUSTOM_OPTION in SUBSCRIPTION_SERVICES
        assert SUBSCRIPTION_SERVICES[-1] == _CUSTOM_OPTION

    def test_known_services_included(self):
        """主要サービスが含まれている"""
        from pages.subscriptions import SUBSCRIPTION_SERVICES

        assert "Netflix" in SUBSCRIPTION_SERVICES
        assert "Spotify" in SUBSCRIPTION_SERVICES
        assert "Nintendo Switch Online" in SUBSCRIPTION_SERVICES
        assert "iCloud+" in SUBSCRIPTION_SERVICES
        assert "ChatGPT Plus" in SUBSCRIPTION_SERVICES
        assert "Kindle Unlimited" in SUBSCRIPTION_SERVICES


class TestServiceCategoryMap:
    """サービス名→カテゴリマッピングのテスト"""

    def test_video_streaming_services(self):
        """動画配信サービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        video_services = ["Netflix", "Amazon Prime Video", "Disney+", "Hulu",
                         "U-NEXT", "YouTube Premium", "ABEMAプレミアム"]
        for service in video_services:
            assert SERVICE_CATEGORY_MAP[service] == "動画配信", f"{service} のカテゴリが不正"

    def test_music_services(self):
        """音楽サービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        music_services = ["Spotify", "Apple Music", "Amazon Music Unlimited",
                         "YouTube Music", "LINE MUSIC"]
        for service in music_services:
            assert SERVICE_CATEGORY_MAP[service] == "音楽", f"{service} のカテゴリが不正"

    def test_gaming_services(self):
        """ゲームサービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        gaming_services = ["Nintendo Switch Online", "PlayStation Plus",
                          "Xbox Game Pass", "Steam"]
        for service in gaming_services:
            assert SERVICE_CATEGORY_MAP[service] == "ゲーム", f"{service} のカテゴリが不正"

    def test_cloud_services(self):
        """クラウドサービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        cloud_services = ["iCloud+", "Google One", "Dropbox", "OneDrive", "Box"]
        for service in cloud_services:
            assert SERVICE_CATEGORY_MAP[service] == "クラウド", f"{service} のカテゴリが不正"

    def test_tool_services(self):
        """ツールサービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        tool_services = ["Adobe Creative Cloud", "Microsoft 365", "Notion",
                        "Figma", "ChatGPT Plus", "GitHub Copilot", "Slack", "Zoom"]
        for service in tool_services:
            assert SERVICE_CATEGORY_MAP[service] == "ツール", f"{service} のカテゴリが不正"

    def test_media_services(self):
        """メディアサービスが正しくマッピングされている"""
        from pages.subscriptions import SERVICE_CATEGORY_MAP

        media_services = ["Kindle Unlimited", "コミックシーモア", "ピッコマ",
                         "NewsPicks", "日経電子版", "楽天マガジン"]
        for service in media_services:
            assert SERVICE_CATEGORY_MAP[service] == "メディア", f"{service} のカテゴリが不正"

    def test_all_services_have_mapping(self):
        """SUBSCRIPTION_SERVICES内の全サービスがマッピングに存在する（カスタム入力除く）"""
        from pages.subscriptions import (
            SUBSCRIPTION_SERVICES, SERVICE_CATEGORY_MAP, _CUSTOM_OPTION, CATEGORIES
        )

        for service in SUBSCRIPTION_SERVICES:
            if service == _CUSTOM_OPTION:
                continue
            assert service in SERVICE_CATEGORY_MAP, f"{service} のマッピングが未定義"
            assert SERVICE_CATEGORY_MAP[service] in CATEGORIES, \
                f"{service} のカテゴリ '{SERVICE_CATEGORY_MAP[service]}' が無効"


class TestDashboardCategoryColors:
    """ダッシュボードのカテゴリ色設定テスト"""

    def test_all_categories_have_colors(self):
        """全カテゴリに色が割り当てられている"""
        from pages.dashboard import CATEGORY_COLORS

        expected_categories = ["動画配信", "音楽", "ゲーム", "クラウド",
                              "ツール", "メディア", "その他"]
        for category in expected_categories:
            assert category in CATEGORY_COLORS, f"{category} に色が未設定"

    def test_colors_are_unique(self):
        """各カテゴリの色が一意である"""
        from pages.dashboard import CATEGORY_COLORS

        colors = list(CATEGORY_COLORS.values())
        assert len(colors) == len(set(colors)), "カテゴリ色に重複がある"

    def test_colors_are_valid_hex(self):
        """色がHEXフォーマットである"""
        from pages.dashboard import CATEGORY_COLORS

        for category, color in CATEGORY_COLORS.items():
            assert color.startswith("#"), f"{category} の色 '{color}' がHEX形式でない"
            assert len(color) == 7, f"{category} の色 '{color}' の長さが不正"


class TestCurrencyFormat:
    """金額フォーマットのテスト"""

    def test_format_currency_integer(self):
        """整数の金額フォーマット"""
        from pages.subscriptions import _format_currency

        assert _format_currency(1980) == "¥1,980"

    def test_format_currency_with_comma(self):
        """桁区切りの確認"""
        from pages.subscriptions import _format_currency

        assert _format_currency(10000) == "¥10,000"
        assert _format_currency(1000000) == "¥1,000,000"

    def test_format_currency_decimal_string(self):
        """文字列の小数値"""
        from pages.subscriptions import _format_currency

        assert _format_currency("1980.50") == "¥1,980"

    def test_format_currency_small(self):
        """少額の金額"""
        from pages.subscriptions import _format_currency

        assert _format_currency(100) == "¥100"

    def test_format_currency_zero(self):
        """ゼロ"""
        from pages.subscriptions import _format_currency

        assert _format_currency(0) == "¥0"

    def test_dashboard_format_currency(self):
        """ダッシュボード側の金額フォーマット"""
        from pages.dashboard import _format_currency

        assert _format_currency(5960) == "¥5,960"
