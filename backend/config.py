"""
アプリケーション設定モジュール

Pydantic Settingsを使用して環境変数から設定値を読み込む。
.envファイルを自動的に読み込み、型安全な設定管理を実現する。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定クラス"""

    # データベース設定
    database_url: str = "postgresql://postgres:postgres@localhost:5432/subscription_manager"

    # JWT認証設定
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_hours: int = 24
    refresh_token_expire_days: int = 30

    # CORS設定
    cors_allowed_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]

    # アプリケーション設定
    app_env: str = "development"
    debug: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """設定のシングルトンインスタンスを返す（キャッシュ付き）"""
    return Settings()
