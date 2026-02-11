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

## タスク2.1: SQLAlchemyモデルとAlembicマイグレーション

### SQLAlchemy ORMモデル定義（2.0スタイル）

**概要**: SQLAlchemy 2.0の`Mapped`と`mapped_column`を使った型安全なモデル定義。
**選定理由**: 型ヒントとORMマッピングを統合でき、IDEの補完が効く。

```python
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

class User(Base):
    __tablename__ = "users"

    # Mapped[型] + mapped_column() で型安全なカラム定義
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # リレーション: cascade="all, delete-orphan" でユーザー削除時にサブスクも削除
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
```

**ハマりやすいポイント**:
- `Mapped[Optional[str]]` と `nullable=True` の両方を指定しないと型チェックが不整合になる
- `relationship` の `back_populates` は双方向で設定する必要がある
- `cascade="all, delete-orphan"` は「親」側（User）のみに設定する

### PostgreSQL ENUM型とPython enum

**概要**: PostgreSQLのENUM型とPythonのenum.Enumを対応させる。
**選定理由**: カテゴリが固定値なので、DB側でも型制約をかけられる。

```python
import enum
from sqlalchemy import Enum

class SubscriptionCategory(str, enum.Enum):
    VIDEO_STREAMING = "動画配信"
    MUSIC = "音楽"

# モデルでの使用
category: Mapped[SubscriptionCategory] = mapped_column(
    Enum(
        SubscriptionCategory,
        name="subscription_category",  # PostgreSQL側のENUM型名
        values_callable=lambda enum: [e.value for e in enum],  # 日本語値を使用
    ),
    nullable=False,
)
```

**ハマりやすいポイント**:
- `values_callable` を指定しないと、Pythonの列挙名（VIDEO_STREAMING）がDB値になる
- `name` パラメータでPostgreSQL側のENUM型名を明示しないと自動生成名になる
- `str` を継承しておくと、Pydanticでの変換やJSON化が楽になる

### Alembic（データベースマイグレーション）

**概要**: SQLAlchemy用のデータベースマイグレーションツール。モデルの変更をSQLに変換してDBに適用する。
**選定理由**: SQLAlchemyモデルとDB構造を同期させる標準ツール。チームでのスキーマ管理に必須。

```bash
# Alembicの初期化（alembicディレクトリとalembic.iniを生成）
poetry run alembic init alembic

# マイグレーション自動生成（モデルとDBの差分を検出）
poetry run alembic revision --autogenerate -m "説明メッセージ"

# マイグレーション実行（最新まで適用）
poetry run alembic upgrade head

# 1つ前に戻す
poetry run alembic downgrade -1

# 現在のバージョン確認
poetry run alembic current
```

**env.pyの設定ポイント**:
```python
# env.py でアプリ設定からDB URLを取得
from backend.config import get_settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# 全モデルをインポートしてメタデータに登録
import backend.models  # noqa: F401
target_metadata = Base.metadata
```

**ハマりやすいポイント**:
- `env.py` で全モデルをインポートしないと `--autogenerate` がテーブルを検出できない
- DDLで手動作成済みのテーブルがある場合、先にDROPしてからマイグレーションを実行する
- `alembic_version` テーブルが管理テーブルとして自動作成される
- `prepend_sys_path = .` が `alembic.ini` にあるので、プロジェクトルートからの相対インポートが可能

### 参考リンク
- [SQLAlchemy 2.0 Mapped Column](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html)
- [Alembic公式チュートリアル](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [PostgreSQL ENUM Type](https://www.postgresql.org/docs/current/datatype-enum.html)

## タスク2.3: Pydanticスキーマ実装

### Pydantic v2 のスキーマ定義

**概要**: FastAPIのリクエスト/レスポンスバリデーションに使うデータスキーマ。
**選定理由**: FastAPIがPydanticを標準採用。型安全なバリデーションと自動APIドキュメント生成。

```python
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal

# リクエストスキーマ: Fieldでバリデーションルールを定義
class SubscriptionCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    monthly_fee: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)

# レスポンススキーマ: from_attributes=True でORMオブジェクトから直接変換
class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service_name: str

# 部分更新スキーマ: 全フィールドをOptionalにする
class SubscriptionUpdate(BaseModel):
    service_name: Optional[str] = Field(None, min_length=1, max_length=100)
```

**ハマりやすいポイント**:
- Pydantic v2 では `orm_mode = True` ではなく `ConfigDict(from_attributes=True)` を使う
- `Field(..., gt=0)` の `...` は必須フィールドを意味する（Ellipsis）
- `Decimal` 型は `max_digits` と `decimal_places` でDB側の `DECIMAL(10,2)` と一致させる
- `exclude_unset=True` を `model_dump()` に渡すと、未指定フィールドを除外できる（部分更新に便利）

### 参考リンク
- [Pydantic v2 Field](https://docs.pydantic.dev/latest/concepts/fields/)
- [Pydantic v2 ConfigDict](https://docs.pydantic.dev/latest/api/config/)

## タスク3: 認証システム実装

### passlib + bcrypt（パスワードハッシュ）

**概要**: passlibはパスワードハッシュの抽象化ライブラリ。bcryptアルゴリズムのラッパーとして使用。
**選定理由**: bcryptは計算コストが高く、ブルートフォース攻撃に強い。passlibで将来のアルゴリズム変更にも対応。

```python
from passlib.context import CryptContext

# bcryptコンテキスト作成
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ハッシュ生成
hashed = pwd_context.hash("password123")  # "$2b$12$..."

# パスワード照合
is_valid = pwd_context.verify("password123", hashed)  # True
```

**ハマりやすいポイント**:
- **bcrypt 5.x と passlib の互換性問題**: bcrypt 5.0 で `__about__` モジュールが削除され、passlibがバージョン検出で失敗する。`bcrypt>=4.0,<5.0` にピン留めが必要
- bcryptは72バイトまでのパスワードしか受け付けない

### python-jose（JWT）

**概要**: PythonのJWT（JSON Web Token）ライブラリ。トークンの生成・検証を行う。
**選定理由**: 暗号化バックエンドが選択可能で、FastAPIドキュメントでも推奨。

```python
from jose import jwt, JWTError
from datetime import datetime, timedelta

# トークン生成
payload = {
    "sub": str(user_id),  # subject: ユーザー識別子
    "type": "access",      # トークン種別（access/refresh）
    "exp": datetime.utcnow() + timedelta(hours=24),  # 有効期限
}
token = jwt.encode(payload, "secret_key", algorithm="HS256")

# トークン検証（期限切れや改ざんを自動検出）
try:
    decoded = jwt.decode(token, "secret_key", algorithms=["HS256"])
except JWTError:
    # 無効なトークン（改ざん、期限切れ等）
    pass
```

**ハマりやすいポイント**:
- `algorithms` パラメータは `decode` 時にリスト形式で指定する（`["HS256"]`）
- `sub` クレームは文字列で格納するのが慣例（`str(user_id)`）
- `exp` はUTCの `datetime` を直接渡せる（python-joseが自動でUNIXタイムスタンプに変換）

### FastAPI依存性注入（認証ミドルウェア）

**概要**: FastAPIの `Depends()` でリクエストごとに認証済みユーザーを自動取得する仕組み。
**選定理由**: デコレータベースではなく関数ベースなので、テストでのモック化が容易。

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# BearerトークンスキームをSwagger UIにも反映
security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="認証が必要です")
    # トークン検証...
    return user

# エンドポイントでの使用
@router.get("/protected")
def protected(user: User = Depends(get_current_user)):
    return {"username": user.username}
```

**ハマりやすいポイント**:
- `HTTPBearer(auto_error=False)` にしないと、トークン未送信時に自動で403が返る（401を返したい場合は自前で処理）
- `Depends()` チェーンで `get_db` → `AuthService` → `User` の依存関係を組み立てる
- Swagger UIで「Authorize」ボタンが自動追加され、Bearerトークンのテストが可能

### トークンブラックリスト

**概要**: ログアウト時にトークンをサーバー側で無効化する仕組み。
**選定理由**: JWTはステートレスのため、サーバー側で無効化するにはブラックリストが必要。

```python
# 開発環境ではインメモリのsetで管理
_token_blacklist: set[str] = set()

# 本番環境ではRedisやDBテーブルでの管理を推奨
# Redis例: redis_client.setex(token, ttl, "blacklisted")
```

**ハマりやすいポイント**:
- インメモリ管理はサーバー再起動でリセットされる
- トークンのTTL（有効期限）と同じ期間だけブラックリストに保持すれば十分

### 参考リンク
- [passlib bcrypt](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html)
- [python-jose](https://python-jose.readthedocs.io/en/latest/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
