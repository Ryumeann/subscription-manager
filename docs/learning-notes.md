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

## タスク4: チェックポイント - 認証とデータモデルのテスト

### pytest（テストフレームワーク）

**概要**: Pythonの標準的なテストフレームワーク。シンプルな構文とパワフルな機能を持つ。
**選定理由**: Pythonプロジェクトのデファクトスタンダード。フィクスチャやパラメタライズドテストが強力。

```bash
# 全テスト実行
poetry run pytest

# 詳細表示（-v）
poetry run pytest -v

# 特定ファイルのみ実行
poetry run pytest backend/tests/test_auth.py

# 特定のテスト関数のみ実行（-k でパターンマッチ）
poetry run pytest -k "test_create_user"

# カバレッジ付きテスト実行
poetry run pytest --cov

# 短いトレースバック表示
poetry run pytest --tb=short
```

**ハマりやすいポイント**:
- テストファイル名は `test_*.py` または `*_test.py` の形式にする
- テスト関数名は `test_*` で始める必要がある
- `assert` 文で検証を行う（unittest の `assertEqual` 等は不要）

### conftest.py（テストフィクスチャ）

**概要**: pytest でテスト間で共有するフィクスチャ（テストデータやセットアップ処理）を定義するファイル。
**選定理由**: テストごとに重複する初期化処理を1箇所にまとめられる。

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

@pytest.fixture(scope="session")
def engine():
    """セッションスコープのエンジン（全テストで共有）"""
    return create_engine("postgresql://...")

@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    """関数スコープのDBセッション（各テスト関数ごとに新規作成）"""
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session  # テスト関数に渡す
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)  # テスト後にクリーンアップ

@pytest.fixture
def test_user(db_session: Session):
    """テスト用ユーザーを作成するフィクスチャ"""
    user = User(username="testuser", email="test@example.com", ...)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
```

**スコープの種類**:
- `function`（デフォルト）: 各テスト関数ごとに実行
- `class`: テストクラスごとに1回実行
- `module`: テストモジュール（ファイル）ごとに1回実行
- `session`: 全テストセッションで1回のみ実行

**ハマりやすいポイント**:
- フィクスチャの引数として他のフィクスチャを指定すると、依存関係を自動解決してくれる
- `yield` を使うとテスト後のクリーンアップ処理を書ける（`try-finally` 相当）
- フィクスチャは `conftest.py` に書くと、同じディレクトリ以下の全テストで自動的に利用可能

### テストデータベース設定

**概要**: 本番DBとは別のテスト専用DBを使って、テストの独立性と安全性を確保する。
**選定理由**: 本番データを壊さず、各テストが独立して実行できる。

```bash
# テスト用データベース作成（Dockerコンテナ経由）
docker exec subscription-manager-db psql -U postgres -c "CREATE DATABASE subscription_manager_test;"

# テスト実行（環境変数で接続先を切り替え）
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/subscription_manager_test poetry run pytest
```

```python
# conftest.py でテスト用設定を上書き
@pytest.fixture(scope="session")
def test_settings():
    return Settings(
        database_url="postgresql://...subscription_manager_test",
        secret_key="test-secret-key",
        # テスト用の設定値
    )
```

**ハマりやすいポイント**:
- テストごとに `Base.metadata.create_all()` と `drop_all()` でテーブルを作り直す
- `scope="function"` でDBセッションを作ると、各テストが独立した環境で実行される
- 本番DBとテストDBで同じポートを使う場合、DB名で区別する

### Pydantic バリデーションテスト

**概要**: Pydanticスキーマのバリデーションルールが正しく機能するかテストする。
**選定理由**: APIの入力検証が期待通りに動くことを保証する。

```python
from pydantic import ValidationError
import pytest

def test_monthly_fee_zero_invalid():
    """金額が0はバリデーションエラー"""
    data = {"service_name": "Test", "monthly_fee": 0, ...}

    with pytest.raises(ValidationError) as exc_info:
        SubscriptionCreate(**data)

    # エラー内容の確認
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("monthly_fee",) for error in errors)
```

**テストパターン**:
- **正常系**: 正しい値でスキーマが生成できることを確認
- **境界値**: 最小値・最大値・ゼロ・負の数などをテスト
- **不正な型**: 文字列を期待している箇所に数値を入れる等
- **必須フィールド**: 必須フィールドを欠いたデータでエラーになるか確認

**ハマりやすいポイント**:
- `ValidationError.errors()` はエラーのリストを返す（複数フィールドでエラーが出る場合）
- `error["loc"]` はタプル形式でフィールド名を持つ（例: `("monthly_fee",)`）
- Pydanticは型変換も行うので、文字列 `"1980"` を `Decimal` に変換できる

### モデルのテストパターン

**概要**: ORMモデルのCRUD操作、リレーション、制約を検証する。
**選定理由**: データベース層の動作が設計通りであることを保証する。

```python
def test_create_subscription(db_session, test_user):
    """サブスクリプション作成テスト"""
    subscription = Subscription(
        user_id=test_user.id,
        service_name="Netflix",
        monthly_fee=Decimal("1980.00"),
        category=SubscriptionCategory.VIDEO_STREAMING,
        start_date=date(2024, 1, 1),
        next_renewal_date=date(2024, 2, 1),
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)

    # 検証
    assert subscription.id is not None
    assert subscription.service_name == "Netflix"
    assert subscription.monthly_fee == Decimal("1980.00")

def test_user_cascade_delete(db_session, test_user):
    """ユーザー削除時のカスケード削除テスト"""
    subscription = Subscription(user_id=test_user.id, ...)
    db_session.add(subscription)
    db_session.commit()
    subscription_id = subscription.id

    # ユーザー削除
    db_session.delete(test_user)
    db_session.commit()

    # サブスクリプションもカスケード削除されていることを確認
    deleted = db_session.query(Subscription).filter_by(id=subscription_id).first()
    assert deleted is None
```

**テストパターン**:
- **CRUD操作**: Create、Read、Update、Delete の基本操作
- **データ永続化**: commit後に再取得してデータが保存されているか確認
- **一意性制約**: unique制約が機能するか（IntegrityErrorの確認）
- **カスケード削除**: リレーション設定でカスケード削除が機能するか
- **デフォルト値**: `created_at` などのデフォルト値が自動設定されるか

### 認証システムのテストパターン

**概要**: JWT認証、パスワードハッシュ、トークンブラックリストの動作を検証する。
**選定理由**: セキュリティ上重要な認証機能が正しく動作することを保証する。

```python
def test_authenticate_user_success(db_session, auth_service, test_user):
    """正しい認証情報でユーザー認証が成功する"""
    authenticated_user = auth_service.authenticate_user("testuser", "testpassword123")
    assert authenticated_user is not None
    assert authenticated_user.id == test_user.id

def test_verify_expired_token(db_session, auth_service, test_user):
    """期限切れトークンは拒否される"""
    expired_token = AuthService.create_access_token(
        test_user.id, expires_delta=timedelta(seconds=-1)
    )
    verified_user = auth_service.verify_token(expired_token)
    assert verified_user is None

def test_logout_user(db_session, auth_service, test_user):
    """ログアウト処理でトークンが無効化される"""
    token = AuthService.create_access_token(test_user.id)

    # ログアウト
    result = auth_service.logout_user(token)
    assert result is True

    # トークン検証が失敗する
    verified_user = auth_service.verify_token(token)
    assert verified_user is None
```

**テストパターン**:
- **正常系**: 正しいクレデンシャルで認証成功
- **認証失敗**: 誤ったパスワード、存在しないユーザー
- **トークン生成**: アクセストークンとリフレッシュトークンの生成
- **トークン検証**: 有効/無効/期限切れ/改ざんトークンの検証
- **トークンブラックリスト**: ログアウト後のトークン無効化
- **エッジケース**: 負のユーザーID、特殊文字を含むユーザー名など

**ハマりやすいポイント**:
- トークンブラックリストはインメモリのため、テスト間で状態が共有される → `setup_method` でクリアする
- 同じタイミングで生成されたトークンは同一になる → `time.sleep(1)` で異なる `exp` クレームを持たせる
- `pytest.raises()` で例外を捕捉してテストする

### pyproject.toml でのpytest設定

**概要**: pytest の設定を `pyproject.toml` に記述してプロジェクト全体で統一する。
**選定理由**: 複数の設定ファイル（pytest.ini、setup.cfg 等）を一元管理できる。

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]          # テストディレクトリ
python_files = ["test_*.py"]           # テストファイルのパターン
python_classes = ["Test*"]             # テストクラスの命名規則
python_functions = ["test_*"]          # テスト関数の命名規則
```

**ハマりやすいポイント**:
- `testpaths` を設定しないと、プロジェクト全体から `test_*.py` を探すため遅くなる
- `pyproject.toml` があれば `pytest.ini` は不要

### テスト実行結果

タスク4で実装したテスト:
- **テストファイル**: 3ファイル（test_auth.py、test_models.py、test_schemas.py）
- **テストケース**: 86個
- **カバレッジ**: 認証システム、データモデル、Pydanticスキーマを網羅

```
backend/tests/test_auth.py      34 テスト（パスワードハッシュ、トークン管理、認証）
backend/tests/test_models.py    14 テスト（User、Subscriptionモデル）
backend/tests/test_schemas.py   38 テスト（認証スキーマ、サブスクリプションスキーマ）
```

**実装したオプションタスク**:
- タスク1.1: プロジェクト基盤のテスト設定（conftest.py、テストDB）
- タスク2.2: データモデルの単体テスト
- タスク2.4: 入力検証の単体テスト
- タスク3.2: 認証システムの単体テスト

### 参考リンク
- [pytest公式ドキュメント](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Pydantic ValidationError](https://docs.pydantic.dev/latest/errors/validation_errors/)

---

## タスク5: サブスクリプション管理API実装

### SubscriptionService（ビジネスロジック層）

**概要**: サブスクリプションのCRUD操作と集計処理を担当するサービスクラス。
**選定理由**: ルーターとビジネスロジックを分離することで、テストのしやすさと再利用性を高める。

```python
class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_subscription(self, user_id: int, data: SubscriptionCreate) -> Subscription:
        """next_renewal_date 未指定なら start_date + 1ヶ月を自動設定"""
        ...

    def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """is_active=True のみ取得"""
        ...

    def update_subscription(self, subscription_id: int, user_id: int, data: SubscriptionUpdate) -> Optional[Subscription]:
        """部分更新: model_dump(exclude_unset=True) で送信フィールドのみ適用"""
        ...

    def delete_subscription(self, subscription_id: int, user_id: int) -> bool:
        """論理削除: is_active=False に設定（物理削除しない）"""
        ...

    def calculate_monthly_total(self, user_id: int) -> Decimal:
        """アクティブなサブスクの月額合計"""
        ...

    def get_category_breakdown(self, user_id: int) -> dict[str, Decimal]:
        """カテゴリ別支出集計 {"動画配信": Decimal("1980.00"), ...}"""
        ...
```

**ハマりやすいポイント**:
- `filter(Subscription.is_active == True)` と `== True` の明示的な比較が必要（SQLAlchemy の式評価のため）
- `model_dump(exclude_unset=True)` を使わないと、未指定フィールドが `None` で上書きされる

### 月末日補正ロジック

**概要**: 月次更新日の自動計算で月末をまたぐ場合の日付補正。
**選定理由**: `dateutil.relativedelta` より標準ライブラリの `calendar.monthrange` を使うことで依存を最小化。

```python
from calendar import monthrange

def _add_one_month(d: date) -> date:
    """1ヶ月加算（月末日を超える場合は翌月末日に補正）"""
    month = d.month + 1
    year = d.year + (month - 1) // 12
    month = ((month - 1) % 12) + 1
    max_day = monthrange(year, month)[1]  # その月の最終日
    day = min(d.day, max_day)
    return date(year, month, day)

# 使用例
_add_one_month(date(2024, 1, 31))  # → date(2024, 2, 29)  閏年
_add_one_month(date(2023, 1, 31))  # → date(2023, 2, 28)  平年
```

### 論理削除パターン

**概要**: is_active フラグを False にするだけでレコードを「削除」する手法。
**選定理由**: 履歴データを保持しつつ、ユーザーには見えないようにする。

```python
def delete_subscription(self, subscription_id: int, user_id: int) -> bool:
    subscription = self.get_subscription_by_id(subscription_id, user_id)
    if subscription is None:
        return False
    subscription.is_active = False  # 物理削除せず論理削除
    self.db.commit()
    return True
```

### FastAPI ルーター実装パターン

**概要**: APIRouter でエンドポイントをモジュール分離し、main.py で登録する。

```python
# routers/subscriptions.py
router = APIRouter(prefix="/subscriptions", tags=["サブスクリプション"])

@router.get("", response_model=list[SubscriptionResponse])
def get_subscriptions(
    current_user: User = Depends(get_current_user),  # JWT認証
    db: Session = Depends(get_db),
) -> list[SubscriptionResponse]:
    ...

@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(...): ...

@router.put("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(subscription_id: int, ...): ...

@router.delete("/{subscription_id}", status_code=status.HTTP_200_OK)
def delete_subscription(subscription_id: int, ...) -> dict: ...

# main.py
from backend.routers import auth, subscriptions
app.include_router(subscriptions.router)
```

**ハマりやすいポイント**:
- `@router.get("")` と `@router.get("/")` は異なる（トレイリングスラッシュの扱い）
- `status_code=HTTP_201_CREATED` は `@router.post` デコレータに指定する
- 404 を返す場合は `raise HTTPException(status_code=404, detail="日本語メッセージ")`

### タスク5 実装サマリー

- **新規ファイル**: 3ファイル
- **テストケース追加**: 33個（累計119個）

```
backend/services/subscription_service.py  # ビジネスロジック
backend/routers/subscriptions.py          # APIエンドポイント
backend/tests/test_subscription_service.py  # 単体テスト33件
```

**実装したオプションタスク**:
- タスク5.2*: サブスクリプション管理の単体テスト（CRUD・集計・次回更新日・エッジケース）

---

## タスク6: ダッシュボードサービス実装

### DashboardService — 集計ロジックの委譲パターン

**概要**: ダッシュボード表示に必要なデータ（月間支出・カテゴリ別内訳・支出推移・更新予定）を集約するサービス。

**なぜこの設計か**:
- SubscriptionService が既に `calculate_monthly_total` や `get_category_breakdown` を持っているため、DashboardService はそれらに委譲してコードの重複を避ける
- ダッシュボード固有の集計（12ヶ月推移、更新予定フィルタ）のみ DashboardService で実装

**コード例（委譲パターン）**:
```python
class DashboardService:
    def __init__(self, db: Session) -> None:
        self._subscription_service = SubscriptionService(db)

    def get_category_breakdown(self, user_id: int) -> dict[str, Decimal]:
        # SubscriptionService に委譲
        return self._subscription_service.get_category_breakdown(user_id)
```

### 月別支出推移の算出ロジック

**課題**: DBに月別履歴データがない（サブスクは現在の状態のみ保持）

**解決策**: アクティブなサブスクの `start_date` を基準に、各月の末日時点での支出を計算

```python
def get_spending_trends(self, user_id: int, months: int = 12) -> list[MonthlySpending]:
    today = date.today()
    subscriptions = ...  # アクティブなサブスク一括取得

    for i in range(months - 1, -1, -1):  # 古い月から昇順
        month = today.month - i
        year = today.year
        while month <= 0:   # 年をまたぐ場合の補正
            month += 12
            year -= 1
        month_end = date(year, month, monthrange(year, month)[1])
        total = sum(s.monthly_fee for s in subscriptions if s.start_date <= month_end, Decimal("0"))
```

**ハマりやすいポイント**:
- `range(months - 1, -1, -1)` で古い月から生成することで、結果を昇順に並べる
- 月が0以下になるケース（例: 今月が3月で i=5 → month=-2）は `while month <= 0` で補正

### ORMオブジェクト → Pydanticスキーマ変換

**課題**: `get_upcoming_renewals` は `list[Subscription]`（ORM）を返すが、`DashboardData.upcoming_renewals` は `list[SubscriptionResponse]`（Pydantic）

**解決策**: `model_validate` で変換

```python
# SubscriptionResponse に ConfigDict(from_attributes=True) が必要
upcoming_renewals=[
    SubscriptionResponse.model_validate(s) for s in upcoming_orm
]
```

**from_attributes=True とは**: PydanticモデルがORMオブジェクトの属性（`obj.field`）から値を読み取れるようにする設定。これがないと dict のみ受け付ける。

### ダッシュボードAPIルーターの実装

```python
router = APIRouter(prefix="/dashboard", tags=["ダッシュボード"])

@router.get("")              # GET /dashboard
@router.get("/categories")   # GET /dashboard/categories
@router.get("/trends")       # GET /dashboard/trends
@router.get("/renewals")     # GET /dashboard/renewals
```

**ハマりやすいポイント**:
- `@router.get("")` はプレフィックス `/dashboard` そのものにマッチ（`/` は不要）
- `response_model=dict[str, Decimal]` のように Python の型を直接 response_model に使える

### タスク6 実装サマリー

- **新規ファイル**: 3ファイル
- **テストケース追加**: 20個（累計139個）

```
backend/services/dashboard_service.py   # DashboardService
backend/routers/dashboard.py            # APIエンドポイント4本
backend/tests/test_dashboard_service.py # 単体テスト20件
```

---

## タスク7: 通知システム実装

### RenewalNotification スキーマ設計

**概要**: 更新予定通知のデータ構造。サブスク情報に加えて「残り日数」と「期限切れフラグ」を持つ。

```python
class RenewalNotification(BaseModel):
    subscription: SubscriptionResponse
    days_until_renewal: int   # 負の値 = 期限切れ（例: -3 は3日前に期限切れ）
    is_overdue: bool          # next_renewal_date が過去の場合 True
```

**なぜ days_until_renewal を持つか**: フロントエンドが「あと○日」「○日前に期限切れ」を表示できるようにするため。

### check_upcoming_renewals の設計判断

**通知対象**: 7日以内 **+ 期限切れ** の両方（要件5.1, 5.4）

- 7日以内: `days_until <= days`（days のデフォルトは 7）
- 期限切れ: `days_until < 0` → 条件式 `days_until <= days` で自動的に含まれる

**ソート**: `days_until_renewal` の昇順（期限切れが先、更新が近い順）

```python
notifications.sort(key=lambda n: n.days_until_renewal)
```

**ハマりやすいポイント**:
- DBクエリで `next_renewal_date` をフィルタせず Python 側で計算する実装にしたことで、
  「期限切れ込みで全取得 → Python でソート」がシンプルに書ける
- `days_until = (sub.next_renewal_date - today).days` は `timedelta.days` を使用（負の値を正しく返す）

### mark_renewal_processed — 次回更新日の自動更新

**概要**: 期限切れのサブスクに対して `next_renewal_date` を1ヶ月進める（要件5.3）

```python
def mark_renewal_processed(self, subscription_id: int) -> bool:
    subscription = db.query(Subscription).filter(
        Subscription.id == subscription_id,
        Subscription.is_active == True,
    ).first()

    if subscription is None:
        return False

    subscription.next_renewal_date = self.calculate_next_renewal_date(subscription)
    self.db.commit()
    return True
```

**calculate_next_renewal_date**: `subscription_service._add_one_month` に委譲。月末補正（1月31日→2月28/29日）も自動で処理される。

### TYPE_CHECKING による循環インポート回避

**問題**: `subscription.py` の `Mapped["User"]` で Pylance が `"User" が定義されていません` と警告

**原因**: SQLAlchemy の双方向リレーションでは循環インポートを避けるため文字列で前方参照するが、Pylance がその文字列を型として解決できない

**解決策**: `TYPE_CHECKING` フラグを使用（型チェック時のみインポート、実行時はスキップ）

```python
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.models.user import User  # 実行時には import されない

class Subscription(Base):
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
```

### datetime.utcnow 非推奨の修正

**問題**: Python 3.12 以降 `datetime.utcnow()` が非推奨

**理由**: `utcnow()` はタイムゾーン情報を持たない naive datetime を返すため、UTC であることが明示されない

**修正方法**: `lambda: datetime.now(timezone.utc)` を使用

```python
# 修正前（非推奨）
default=datetime.utcnow

# 修正後
from datetime import datetime, timezone
default=lambda: datetime.now(timezone.utc)
```

**なぜ lambda が必要か**: SQLAlchemy の `default=` は呼び出し可能オブジェクト（callable）を受け取る。`datetime.now(timezone.utc)` は即時評価されてしまうため、毎回新しい値を生成するには `lambda` でラップする。

### タスク7 実装サマリー

- **新規ファイル**: 3ファイル
- **テストケース追加**: 20個（累計159個）

```
backend/schemas/notification.py           # RenewalNotification スキーマ
backend/services/notification_service.py  # NotificationService
backend/tests/test_notification_service.py # 単体テスト20件
```

**合わせて修正した既存の問題**:
- `backend/models/subscription.py`: TYPE_CHECKING による前方参照修正、utcnow 非推奨修正
- `backend/models/user.py`: utcnow 非推奨修正

---

## タスク8: ログサービスとグローバルエラーハンドラー実装

### Python 標準 logging モジュールによる構造化JSONログ

**概要**: `python-json-logger` などの外部ライブラリを使わず、標準 `logging.Formatter` をサブクラス化してJSONログを実装する。

**なぜこの設計か**:
- 依存ライブラリを増やさずに済む
- `logging.LogRecord` の `extra` 引数を使うと、フィールドを自由に追加できる

```python
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)  # カスタムフィールドをマージ
        return json.dumps(log_data, ensure_ascii=False)

# 使用側: extra={"extra_fields": {...}} で追加フィールドを渡す
logger.error("エラー", extra={"extra_fields": {"error_type": "ValueError"}})
```

**ハマりやすいポイント**:
- `extra={"key": "value"}` は LogRecord に直接 `record.key` として追加される
- ただし `extra` のキーが LogRecord の既存属性と衝突するとエラーになるため、`extra_fields` のように一つのキーにまとめるのが安全

### RotatingFileHandler によるログローテーション

**概要**: ログファイルが一定サイズを超えたら古いファイルに退避する仕組み。

```python
import logging.handlers

handler = logging.handlers.RotatingFileHandler(
    "logs/app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,              # 最大5世代保持（app.log.1 〜 app.log.5）
    encoding="utf-8",
)
```

**ログファイルのディレクトリ自動作成**:
```python
os.makedirs(os.path.dirname(log_file), exist_ok=True)
```

### ロガーの重複ハンドラー防止

**問題**: `logging.getLogger(name)` は同名のロガーを返すため、複数回 `LoggingService` を生成するとハンドラーが累積して同じログが複数回出力される

**解決策**: `if not self.logger.handlers:` で初回のみハンドラーを追加する

```python
self.logger = logging.getLogger(logger_name)
if not self.logger.handlers:
    self._setup_handlers(log_file)
```

### FastAPI グローバルエラーハンドラー

**概要**: `app.add_exception_handler(ExcClass, handler_func)` で全APIの例外を統一フォーマットで返す。

**3種類のハンドラー**:
| 例外クラス | HTTP Status | error_code |
|---|---|---|
| `HTTPException` | 元の status_code | `HTTP_404` 等 |
| `RequestValidationError` | 422 | `VALIDATION_ERROR` |
| `Exception` | 500 | `INTERNAL_SERVER_ERROR` |

```python
# main.py
register_error_handlers(app)  # ルーター登録前に呼ぶこと
app.include_router(auth.router)
```

**ハマりやすいポイント**:
- `@app.exception_handler` デコレータを関数内で使うと Pylance が「関数が参照されていない」と誤検知する → `app.add_exception_handler()` を使えば解決
- 500 ハンドラーの引数は `Exception` を継承する全クラスに適用されるが、`HTTPException` より後に登録すると `HTTPException` もキャッチしてしまう → `add_exception_handler` は登録順ではなく型の特異性で優先順位が決まる

### FastAPI TestClient によるエラーハンドラーテスト

**概要**: 本番のDBや認証なしで、エラーハンドラーだけをテストするミニアプリを作成する。

```python
def _create_test_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise-500")
    def raise_500() -> dict:
        raise RuntimeError("内部エラー")

    return app

# raise_server_exceptions=False: TestClient が 5xx を例外として再送出しない
client = TestClient(_create_test_app(), raise_server_exceptions=False)
response = client.get("/raise-500")
assert response.status_code == 500
```

### Python 3.10 と datetime.fromisoformat の互換性

**問題**: Pydantic v2 が UTC datetime を `"2024-01-01T00:00:00Z"` 形式で出力するが、Python 3.10 の `datetime.fromisoformat()` は `Z` サフィックスを解釈できない（3.11+ で対応）

**対処法**: テスト時に `Z` を `+00:00` に置換する

```python
dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
```

### タスク8 実装サマリー

- **新規ファイル**: 5ファイル
- **テストケース追加**: 33個（累計192個）

```
backend/schemas/error.py               # ErrorResponse スキーマ
backend/services/logging_service.py    # JsonFormatter + LoggingService
backend/error_handlers.py              # グローバルエラーハンドラー
backend/tests/test_logging_service.py  # ログサービステスト17件
backend/tests/test_error_handlers.py   # エラーハンドラーテスト16件
```

---

## タスク9: セキュリティミドルウェア実装

### Starlette BaseHTTPMiddleware

**概要**: FastAPI（内部はStarlette）のミドルウェア基底クラス。全リクエスト/レスポンスに共通処理を挟める。

**選定理由**: FastAPI組み込みの仕組みで、外部ライブラリ不要。`dispatch` メソッドをオーバーライドするだけでシンプルに実装できる。

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class MyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # リクエスト前処理
        response = await call_next(request)  # 次のミドルウェア/ルーターに処理を渡す
        # レスポンス後処理（ヘッダー追加など）
        response.headers["X-Custom"] = "value"
        return response
```

**ミドルウェアの登録順序の注意点**: `add_middleware()` はスタック構造（後入れ先出し）。最後に登録したものが最初に実行される。

```python
app.add_middleware(CORSMiddleware, ...)       # 3番目に実行
app.add_middleware(CSRFProtectionMiddleware)  # 2番目に実行
app.add_middleware(SecurityHeadersMiddleware) # 1番目に実行（レスポンスに最後に触れる）
```

---

### CORSMiddleware（Cross-Origin Resource Sharing）

**概要**: ブラウザのSame-Origin Policyを制御する仕組み。異なるオリジン（ドメイン・ポート・プロトコル）からのAPIアクセスを許可/拒否する。

**選定理由**: Streamlit（port 8501）からFastAPI（port 8000）にアクセスするためにCORS設定が必須。FastAPI標準提供の `CORSMiddleware` を使用。

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # 許可するオリジン
    allow_credentials=True,                  # Cookie/Authorizationヘッダーを許可
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # 許可するHTTPメソッド
    allow_headers=["Authorization", "Content-Type"], # 許可するリクエストヘッダー
)
```

**プリフライトリクエスト**: ブラウザは状態変更リクエスト前に `OPTIONS` メソッドで事前確認する。`CORSMiddleware` が自動で処理する。

---

### セキュリティヘッダー（XSS・クリックジャッキング防止）

**概要**: HTTPレスポンスヘッダーでブラウザのセキュリティ機能を制御する。

| ヘッダー | 効果 |
|---|---|
| `X-Content-Type-Options: nosniff` | MIMEスニッフィング防止（XSS対策） |
| `X-Frame-Options: DENY` | iframe埋め込み禁止（クリックジャッキング防止） |
| `X-XSS-Protection: 1; mode=block` | 旧ブラウザのXSSフィルター有効化 |
| `Content-Security-Policy: default-src 'none'` | スクリプト読み込み元を制限（XSS対策） |
| `Strict-Transport-Security` | HTTPS強制（HSTS） |
| `Referrer-Policy` | リファラー情報の送信制限 |

---

### CSRF（Cross-Site Request Forgery）保護

**概要**: 悪意あるサイトがユーザーの認証情報を悪用して不正リクエストを送る攻撃への対策。

**このAPIでCSRFが問題になりにくい理由**: JWT認証をAuthorizationヘッダー（Bearer token）で行っているため、ブラウザが自動送信するCookieベースのCSRFとは構造が異なる。しかし将来的な変更を見据えてOriginヘッダー検証を実装。

**Originヘッダー検証の仕組み**:
```python
# 状態変更リクエスト（POST/PUT/DELETE）のみ検証
if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
    origin = request.headers.get("origin")
    if origin is not None and origin not in allowed_origins:
        return JSONResponse(status_code=403, ...)
```

**ハマりやすいポイント**: `curl` 等のHTTPクライアントはOriginヘッダーを送らないため、`origin is not None` のチェックが必要。Noneのときは許可する設計にしないと開発・テストが困難になる。

---

### タスク9 実装サマリー

- **新規ファイル**: 3ファイル
- **テストケース追加**: 19個

```
backend/middleware/__init__.py         # ミドルウェアパッケージ
backend/middleware/security.py         # SecurityHeadersMiddleware + CSRFProtectionMiddleware
backend/tests/test_security.py         # セキュリティミドルウェアテスト19件
```

**変更ファイル**:
```
backend/config.py    # cors_allowed_origins 設定を追加
backend/main.py      # CORSMiddleware / CSRF / SecurityHeaders を登録
```

---

## タスク11: Streamlitフロントエンド実装

### Streamlit（Webアプリフレームワーク）

**概要**: Pythonスクリプトを最小限のコードでWebアプリに変換するフレームワーク。HTMLやJavaScriptを書かずにUIを構築できる。
**選定理由**: データサイエンス・分析ダッシュボードに特化。Plotlyとの統合が標準的。Pythonだけで完結する。

```bash
# 起動
streamlit run frontend/app.py
# → http://localhost:8501 でアクセス
```

**基本的な使い方**:
```python
import streamlit as st

# ページ設定（最初のStreamlitコマンドである必要がある）
st.set_page_config(page_title="アプリ名", layout="wide")

# UI要素
st.title("タイトル")
st.metric(label="月間支出", value="¥5,000")
col1, col2 = st.columns(2)
with col1:
    st.write("左カラム")

# フォーム（送信時に一括処理）
with st.form("my_form"):
    name = st.text_input("名前")
    submitted = st.form_submit_button("送信")
if submitted:
    st.write(f"送信: {name}")

# セッション状態管理
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ページ再レンダリング
st.rerun()
```

**ハマりやすいポイント**:
- `st.set_page_config()` は必ずスクリプト内の最初のStreamlitコマンドであること
- `st.rerun()` を呼ぶとスクリプト全体が再実行される
- フォーム外の `st.button()` はクリックごとにスクリプトが再実行される（フォームで囲むと送信時のみ実行）
- Streamlit は `frontend/app.py` の起動時に `frontend/` をsys.pathに追加するため、`from pages import xxx` のように相対インポートが使える

### Plotly（インタラクティブグラフ）

**概要**: インタラクティブなグラフライブラリ。ホバー表示・ズームなどが標準搭載。
**選定理由**: Streamlitの `st.plotly_chart()` と組み合わせが最良。円グラフ・折れ線グラフを簡潔に実装できる。

```python
import plotly.graph_objects as go
import streamlit as st

# 円グラフ（ドーナツ型）
fig = go.Figure(data=[go.Pie(
    labels=["動画配信", "音楽", "ゲーム"],
    values=[1980, 980, 500],
    hole=0.4,  # ドーナツ型にする割合
    hovertemplate="%{label}: ¥%{value:,.0f}<extra></extra>",
)])
st.plotly_chart(fig, use_container_width=True)

# 折れ線グラフ
fig = go.Figure(data=[go.Scatter(
    x=["2024/01", "2024/02"],
    y=[3000, 3500],
    mode="lines+markers",
)])
st.plotly_chart(fig, use_container_width=True)
```

### requestsライブラリ（HTTPクライアント）

**概要**: PythonのHTTPクライアントライブラリ。同期的なHTTPリクエストを送信する。
**選定理由**: StreamlitのサーバーサイドコードからバックエンドAPIを呼び出すのに使用。シンプルなAPIで使いやすい。

```python
import requests

# JWTトークン付きGETリクエスト
response = requests.get(
    "http://localhost:8000/subscriptions",
    headers={"Authorization": f"Bearer {token}"},
)
data = response.json()

# POSTリクエスト（JSONボディ）
response = requests.post(
    "http://localhost:8000/auth/login",
    json={"username": "user", "password": "pass"},
)
```

**ハマりやすいポイント**:
- `requests` はサーバーサイドからの呼び出し（Originヘッダーなし）なので、CSRFミドルウェアの検証をパスする
- `response.ok` は2xx系のとき `True`
- `response.json()` はContent-Typeが空のとき例外になるため `response.content` で確認してから呼ぶ

### フロントエンドのファイル構成

**新規ファイル**:
```
frontend/app.py              # エントリポイント（セッション管理・ルーティング）
frontend/api_client.py       # バックエンドAPI呼び出しクライアント
frontend/pages/__init__.py   # パッケージ定義
frontend/pages/login.py      # ログイン画面
frontend/pages/dashboard.py  # ダッシュボード（グラフ・サマリー・更新予定）
frontend/pages/subscriptions.py  # サブスクリプション管理（CRUD）
```

**トークンリフレッシュの実装パターン**:
```python
def _get_data(client):
    try:
        return client.get_xxx(st.session_state.access_token)
    except APIError as e:
        if e.status_code == 401:  # トークン期限切れ
            result = client.refresh_token(st.session_state.refresh_token)
            st.session_state.access_token = result["access_token"]
            return client.get_xxx(st.session_state.access_token)
```

## タスク12: サービス名プルダウン実装

### Streamlit selectbox の検索機能

**概要**: `st.selectbox` はユーザーがキーボードで文字を入力すると前方一致でリストをフィルタリングできる。テキスト入力不要で検索UIを実現できる。

**選定理由**: 既知のサービス名を選択可能にしつつ、前方一致検索で素早く絞り込める。「その他（直接入力）」オプションを末尾に設けることで任意のサービス名も登録可能。

```python
# index=None にすると未選択状態で起動（placeholder が表示される）
selected = st.selectbox(
    "サービス名 *",
    SUBSCRIPTION_SERVICES,
    index=None,
    placeholder="サービスを選択または入力...",
)

# 「その他」選択時のみテキスト入力を表示
if selected == "その他（直接入力）":
    service_name = st.text_input("サービス名を入力 *", max_chars=100)
else:
    service_name = selected or ""
```

**編集フォームでの初期値設定**:
```python
# 既存データがリストにあればそのインデックスを、なければ「その他」のインデックスを使う
if current_name in SUBSCRIPTION_SERVICES:
    idx = SUBSCRIPTION_SERVICES.index(current_name)
else:
    idx = SUBSCRIPTION_SERVICES.index("その他（直接入力）")

selected = st.selectbox("サービス名", SUBSCRIPTION_SERVICES, index=idx)
```

**ハマりやすいポイント**:
- `st.form` の中では `st.selectbox` の値変化でリアルタイムに `st.text_input` を表示/非表示にできない（フォーム送信前は再レンダリングされない）
- `index=None` は Streamlit 1.x 以降で有効。古いバージョンでは `index=0` を使う必要がある

## タスク11.5: フロントエンド機能の単体テスト

### フロントエンドテストの方針

**概要**: Streamlitは直接的な単体テストが難しい（UIレンダリングがサーバー上で行われるため）。そのため、テスト可能なロジック部分を切り出してテストする。

**テスト対象**:
1. `APIClient` — HTTPリクエストをモック(`unittest.mock.patch`)で差し替えてテスト
2. 定数・マッピング — `CATEGORIES`, `SUBSCRIPTION_SERVICES`, `SERVICE_CATEGORY_MAP` の整合性
3. ユーティリティ関数 — `_format_currency()` の出力

**選定理由**: Streamlit専用のテストフレームワーク（`streamlit.testing`）もあるが、APIクライアントと定数のテストは標準のpytestとmockで十分。

```python
# frontendディレクトリをパスに追加してインポートする
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api_client import APIClient, APIError

# requests.post をモック化してHTTPリクエストを差し替え
from unittest.mock import MagicMock, patch

@patch("api_client.requests.post")
def test_login(mock_post, client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"access_token": "abc"}
    mock_post.return_value = mock_response
    result = client.login("user", "pass")
    assert result["access_token"] == "abc"
```

**ハマりやすいポイント**:
- `sys.path` に `frontend/` を追加しないと `from api_client import ...` が失敗する
- `pyproject.toml` の `testpaths` に `frontend/tests` を追加しないと `poetry run pytest` で検出されない

## タスク12.2: 統合テスト

### FastAPI TestClient によるE2Eテスト

**概要**: FastAPIの`TestClient`（内部でStarlette/httpxを使用）を使い、実際のHTTPリクエストを送信してAPI全体のフローを検証する。

**選定理由**: 単体テストでは検出できないルーター・依存性注入・ミドルウェアの結合不良を検出できる。

```python
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db

# テスト用DBセッションで上書き
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# ログイン → トークン取得 → CRUD → ダッシュボード の一連のフロー
response = client.post("/auth/login", json={...})
token = response.json()["access_token"]
header = {"Authorization": f"Bearer {token}"}
response = client.get("/subscriptions", headers=header)
```

**テスト項目**:
- 認証フロー: ログイン成功/失敗、ログアウト後のトークン無効化、トークンリフレッシュ
- CRUD一連フロー: 作成→一覧取得→更新→削除→削除後の一覧
- ダッシュボード: 空データ・データあり時のレスポンス
- セキュリティ: 未認証アクセス拒否、無効トークン拒否、セキュリティヘッダー、ユーザー間のデータ分離

**ハマりやすいポイント**:
- `_token_blacklist` がインメモリの `set()` なのでテスト間でリセットが必要（`_token_blacklist.clear()`）
- JWT は同一秒に同一ペイロードで生成すると同じ文字列になるため、トークン文字列の比較テストは不安定になる
- `app.dependency_overrides[get_db]` でDBセッションを差し替えないと本番DBに書き込んでしまう

## タスク12.3: Dockerファイルとデプロイ設定

### Dockerfileの基本構成

**概要**: Dockerfileはコンテナイメージの「設計図」。アプリの実行環境ごとパッケージにして、どの環境でも同じように動かせるようにする。

**選定理由**: ECS Fargateにデプ��イするにはコンテナイメージが必要。Dockerfileでイメージの作り方を定義する。

**Dockerfileの主要命令**:
```dockerfile
FROM python:3.10-slim   # ベースイメージ（OS + ランタイム）
RUN apt-get install ...  # ビルド時に実行するコマンド
WORKDIR /app             # 作業ディレクトリの設定
COPY src/ ./src/         # ローカル → コンテナへファイルコピー
ENV APP_ENV=production   # 環境変数の初期値
EXPOSE 8000              # ポート宣言（ドキュメント目的）
CMD ["uvicorn", ...]     # コンテナ起動時のコマンド
```

**キャッシュ最適化テクニック**:
```dockerfile
# 依存関係ファイルだけ先にコピー → インストール → ソースコードをコピー
# ソースコード変更時に依存関係の再インストールをスキップできる
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main
COPY backend/ ./backend/   # ← ここだけ再実行される
```

### docker-compose.prod.yml

**概要**: 複数コンテナ（バックエンド・フロントエンド・DB）を一括起動する設定ファイル。

**コンテナ間通信**:
```yaml
# Docker Compose内ではサービス名がホスト名になる
# localhost ではなくサービス名でアクセスする
DATABASE_URL: postgresql://postgres:postgres@db:5432/subscription_manager
#                                              ^^
#                                   サービス名 "db" がホスト名
```

**depends_on**: サービスの起動順序を制御する
```yaml
backend:
  depends_on:
    db:
      condition: service_healthy  # DBのヘルスチェック通過後に起動
```

### .dockerignore

**概要**: `.gitignore` のDocker版。`COPY` コマンドで除外するファイルを指定する。

**目的**:
1. イメージサイズの削減（.git、docs、テストファイルを含めない）
2. セキュリティ（.env をコンテナに含めない）
3. ビルド速度の向上（転送するファイルを減らす）

### ビルドコマンド

```bash
# 個別ビルド
docker build -f Dockerfile.backend -t subscription-manager-backend .
docker build -f Dockerfile.frontend -t subscription-manager-frontend .

# docker-compose で一括ビルド＋起��
docker compose -f docker-compose.prod.yml up --build
```

**ハマりやすいポイント**:
- `--host 0.0.0.0` を付けないとコンテナ外部からアクセスできない（127.0.0.1 はコンテナ内のみ）
- Poetry の `virtualenvs.create false` を設定しないとコンテナ内に無駄な仮想環境ができる
- `COPY` の左側はDockerfileからの相対パス、右側はWORKDIR基準
