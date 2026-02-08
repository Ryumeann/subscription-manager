# 学習ノート

## タスク1: プロジェクト基盤とコア設定

### Poetry（パッケージ管理）

**概要**: Pythonの依存関係管理・パッケージングツール。pip + venv の代替。
**選定理由**: pyproject.toml一つで依存関係・ビルド設定・ツール設定を統合管理できる。lockファイルで再現性を保証。

```bash
# 依存関係のインストール（poetry.lockがあれば正確なバージョンを再現）
poetry install

# パッケージ追加
poetry add fastapi

# 開発用パッケージ追加（--groupオプション）
poetry add --group dev pytest

# Poetry環境でコマンド実行
poetry run uvicorn backend.main:app --reload
```

**ハマりやすいポイント**:
- `poetry install` は仮想環境を自動作成する。`poetry env info` で確認可能
- pyproject.tomlの `[tool.poetry.dependencies]` に python バージョン制約を必ず指定する

### Pydantic Settings（環境変数管理）

**概要**: Pydanticの設定管理拡張。環境変数や.envファイルを型安全に読み込む。
**選定理由**: FastAPIと同じPydanticベースで統一。バリデーション付きの設定管理。

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql://..."  # 環境変数 DATABASE_URL から自動読み込み
    debug: bool = True                       # 型変換も自動（文字列"true" → bool True）

    model_config = SettingsConfigDict(
        env_file=".env",           # .envファイルから読み込み
        case_sensitive=False,      # 環境変数名の大文字小文字を区別しない
    )
```

**ハマりやすいポイント**:
- `pydantic-settings` は Pydantic v2 から別パッケージに分離された
- `lru_cache` で設定インスタンスをキャッシュすると、毎回.envを読まなくて済む

### SQLAlchemy（ORM）

**概要**: PythonのORMライブラリ。Pythonクラスとデータベーステーブルをマッピング。
**選定理由**: FastAPIとの相性が良く、PostgreSQLサポートが充実。

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# エンジン作成（接続プール管理）
engine = create_engine("postgresql://...", pool_pre_ping=True)

# セッションファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORMモデルの基底クラス（SQLAlchemy 2.0スタイル）
class Base(DeclarativeBase):
    pass
```

**ハマりやすいポイント**:
- SQLAlchemy 2.0では `DeclarativeBase` を使う（1.x の `declarative_base()` は非推奨）
- `pool_pre_ping=True` を設定しないと、PostgreSQLのidle接続タイムアウトで接続エラーが発生する
- `autoflush=False` にしないと、クエリ前に意図しないINSERT/UPDATEが発行される場合がある

### Docker Compose（開発環境）

**概要**: 複数コンテナの定義・実行ツール。ここではPostgreSQLの開発環境として使用。
**選定理由**: ローカルにPostgreSQLをインストールせずに開発環境を構築できる。

```bash
# PostgreSQLコンテナ起動
docker compose up -d

# ログ確認
docker compose logs db

# コンテナ停止（データは保持）
docker compose down

# コンテナ停止 + データ削除
docker compose down -v
```

**ハマりやすいポイント**:
- `docker-entrypoint-initdb.d/` にSQLファイルをマウントすると初回起動時に自動実行される
- データを完全にリセットしたい場合は `docker compose down -v` でボリュームも削除する
- ポート5432が既に使われている場合はポートマッピングを変更する

### FastAPI（Webフレームワーク）

**概要**: Python製の高速なWebフレームワーク。自動API仕様書生成（OpenAPI/Swagger）。
**選定理由**: Pydanticとの統合、自動バリデーション、非同期サポート、自動APIドキュメント生成。

```bash
# 開発サーバー起動（--reloadでホットリロード有効）
poetry run uvicorn backend.main:app --reload

# APIドキュメント確認
# http://localhost:8000/docs    (Swagger UI)
# http://localhost:8000/redoc   (ReDoc)
```

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI(title="サブスクリプション管理API")

# 依存性注入でDBセッションを自動管理
@app.get("/health")
def health_check():
    return {"status": "ok"}
```

**ハマりやすいポイント**:
- `backend.main:app` の形式は `パッケージ.モジュール:変数名`
- `--reload` は開発時のみ使用（本番では不要）

### 参考リンク
- [Poetry公式ドキュメント](https://python-poetry.org/docs/)
- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0ドキュメント](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Docker Compose](https://docs.docker.com/compose/)
