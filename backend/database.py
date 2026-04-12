"""
データベース接続モジュール

SQLAlchemyを使用してPostgreSQLへの接続を管理する。
- Engine: データベースへの接続プールを管理
- SessionLocal: 各リクエストごとのDBセッションを生成するファクトリ
- Base: 全ORMモデルの基底クラス
- get_db: FastAPIの依存性注入用ジェネレータ
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings

settings = get_settings()

# SQLAlchemyエンジン作成
# pool_pre_ping=True: 接続プールから取得時にDBへの接続確認を行い、切断された接続を自動再接続する
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# セッションファクトリ
# autocommit=False: 明示的にcommit()を呼ぶまでトランザクションを保持
# autoflush=False: 明示的にflush()を呼ぶまでSQLを発行しない
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """全ORMモデルの基底クラス"""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPIの依存性注入用データベースセッションジェネレータ。

    リクエストごとにセッションを生成し、処理完了後に自動クローズする。
    使用例:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
