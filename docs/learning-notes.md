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
