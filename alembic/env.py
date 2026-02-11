"""
Alembic マイグレーション環境設定

アプリケーションの Settings からDB接続URLを取得し、
backend.models の全モデルメタデータを自動検出対象に設定する。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from backend.config import get_settings
from backend.database import Base

# 全モデルをインポートしてメタデータに登録する
import backend.models  # noqa: F401

# Alembic Config オブジェクト
config = context.config

# アプリケーション設定からDB URLを取得してAlembicに設定
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python ログ設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 用のメタデータ
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """オフラインモードでマイグレーションを実行（SQL出力のみ）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンラインモードでマイグレーションを実行（DB直接接続）"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
