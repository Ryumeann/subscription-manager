# サブスクリプション管理アプリ

Netflix、Spotify、Kindle Unlimited 等のサブスクリプション契約を一元管理する Web アプリケーション。月額合計やカテゴリ別支出をダッシュボードで可視化し、更新予定をひと目で把握できます。

## 主な機能

- ユーザー新規登録・ログイン（JWT認証）
- サブスクリプションのCRUD（プルダウンから54サービスを選択 + 自由入力）
- カテゴリ自動連動（動画配信・音楽・ゲーム・クラウド・ツール・メディア・その他）
- ダッシュボード
  - 月間総支出・契約中サービス数・7日以内の更新予定
  - カテゴリ別支出円グラフ
  - 月別支出推移グラフ（過去12ヶ月）
- スマホ・タブレット対応のレスポンシブ表示

## 技術スタック

| 区分 | 技術 |
|------|------|
| バックエンド | FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2 |
| フロントエンド | Streamlit 1.41 + Plotly |
| データベース | PostgreSQL 16（開発: Docker / 本番: Supabase） |
| 認証 | JWT（HS256）+ bcrypt |
| マイグレーション | Alembic |
| パッケージ管理 | Poetry |
| テスト | pytest（カバレッジ 91%） |
| インフラ | Docker / ECS Fargate（後続フェーズ）|

## 開発環境

- Python 3.10.12
- WSL2 (Ubuntu 22.04)
- Docker Compose（PostgreSQL）

## クイックスタート

### 1. セットアップ

```bash
# 依存関係インストール
poetry install

# 環境変数ファイルを作成
cp .env.example .env

# DB起動（Docker）
docker compose up -d

# マイグレーション実行
poetry run alembic upgrade head
```

### 2. 起動

```bash
# ターミナル1: バックエンド
poetry run uvicorn backend.main:app --reload

# ターミナル2: フロントエンド
poetry run streamlit run frontend/app.py
```

ブラウザで http://localhost:8501 を開いてください。新規登録でアカウントを作成すると自動ログインしてダッシュボードに遷移します。

### 3. APIドキュメント（開発環境のみ）

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

本番環境（`APP_ENV=production`）ではこれらのエンドポイントは404を返します。

## テスト

```bash
# 全テスト実行
poetry run pytest

# カバレッジ付き
poetry run pytest --cov=backend --cov=frontend

# 特定ファイルのみ
poetry run pytest backend/tests/test_auth.py
```

## ディレクトリ構成

```
backend/
├── main.py              # FastAPI エントリポイント
├── config.py            # アプリケーション設定（pydantic-settings）
├── database.py          # SQLAlchemy エンジン・セッション
├── dependencies.py      # 依存性注入（認証等）
├── error_handlers.py    # グローバル例外ハンドラ
├── models/              # SQLAlchemy ORM モデル
├── schemas/             # Pydantic スキーマ
├── services/            # ビジネスロジック層
├── routers/             # FastAPI ルートハンドラ
├── middleware/          # CORS・CSRF・セキュリティヘッダ
└── tests/               # pytest テストスイート

frontend/
├── app.py               # Streamlit エントリポイント
├── api_client.py        # FastAPI へのHTTPクライアント
├── views/               # 各画面（ログイン・ダッシュボード・サブスク管理）
└── tests/               # フロントエンド単体テスト

scripts/
├── load_prod_env.sh     # SSM経由で本番DB接続を環境変数にロード
└── unload_prod_env.sh   # 本番関連の環境変数をクリア

alembic/versions/        # データベースマイグレーション履歴
docs/                    # 要件・設計・タスク・学習ノート
```

## ドキュメント

- [docs/requirements.md](docs/requirements.md) - 要件定義（受け入れ基準）
- [docs/design.md](docs/design.md) - 設計（コンポーネント・データモデル・スキーマ）
- [docs/tasks.md](docs/tasks.md) - 実装タスクの進捗
- [docs/learning-notes.md](docs/learning-notes.md) - 技術選定の理由・ハマりどころ
- [CLAUDE.md](CLAUDE.md) - 開発ルール・本番運用手順
