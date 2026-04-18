# CLAUDE.md

このファイルは、Claude Code がこのリポジトリで作業する際のガイドラインです。

## プロジェクト概要

サブスクリプション管理Webアプリケーション（サブスクリプション管理アプリ）。Netflix、Spotify などのサブスクリプション契約を一元管理するシステム。日本語インターフェースで、通貨は日本円（JPY）表示。現在は設計フェーズ — ディレクトリ構造と設計ドキュメントは存在するが、実装コードはまだ無い。

## 技術スタック

- **バックエンド**: FastAPI（Python 3.10）+ SQLAlchemy ORM + Pydantic バリデーション
- **フロントエンド**: Streamlit + Plotly チャート
- **データベース**: PostgreSQL（本番環境は Supabase）
- **認証**: JWT（アクセストークン24時間、リフレッシュトークン30日）+ bcrypt パスワードハッシュ
- **パッケージ管理**: Poetry
- **テスト**: pytest
- **インフラ**:    
        - 開発環境: Docker PostgreSQL（VS Code拡張機能でDB操作）
        - 初期リリース: ECS Fargate + Supabase/Neon
        - スケール後: ECS Fargate + RDS

## よく使うコマンド

```bash
poetry install                          # 依存関係のインストール
poetry run uvicorn backend.main:app     # FastAPI バックエンド起動
streamlit run frontend/app.py           # Streamlit フロントエンド起動
poetry run pytest                       # 全テスト実行
poetry run pytest backend/tests/test_auth.py  # 単一テストファイル実行
poetry run pytest -k "test_name"        # テスト名で単一テスト実行
poetry run pytest --cov                 # カバレッジ付きテスト実行
```

## アーキテクチャ

3層モノリシックアーキテクチャ:

```
Streamlit（プレゼンテーション層） → FastAPI（ビジネスロジック層） → SQLAlchemy + PostgreSQL（データ層）
```

### バックエンド構成 (`backend/`)

- `models/` — SQLAlchemy ORM モデル（User、Subscription、SubscriptionCategory 列挙型）
- `routers/` — FastAPI ルートハンドラー（認証、サブスクリプション、ダッシュボード）
- `services/` — ビジネスロジック層:
  - **AuthService** — JWTトークンライフサイクル、パスワードハッシュ、トークンブラックリスト
  - **SubscriptionService** — CRUD、月間合計、カテゴリ集計、更新日計算
  - **DashboardService** — 分析データ集計、12ヶ月推移、7日以内更新予定
  - **NotificationService** — 更新検知、次回更新日の自動計算
  - **LoggingService** — 構造化JSONログ（JSON形式、コンソール出力 + ファイル出力）、ECS Fargate標準出力でCloudWatch Logsに集約
- `tests/` — pytest テストスイート（目標: カバレッジ90%以上）

### フロントエンド構成 (`frontend/`)

- Streamlit ページ: ログイン、ダッシュボード（サマリー + チャート）、サブスクリプション管理フォーム
- セッション管理: `st.session_state` を使用
- グラフ: Plotly（円グラフ、折れ線グラフ）

### API エンドポイント

- 認証: `POST /auth/login`、`POST /auth/logout`、`POST /auth/refresh`
- サブスクリプション: `GET|POST /subscriptions`、`PUT|DELETE /subscriptions/{id}`
- ダッシュボード: `GET /dashboard`、`GET /dashboard/categories`、`GET /dashboard/trends`、`GET /dashboard/renewals`

## 設計上の重要な決定事項

- **サブスクリプションカテゴリ**: 固定の列挙型 — 動画配信、音楽、ゲーム、その他
- **通貨**: 全金額は日本円（JPY）、`Decimal(10,2)` 型、¥記号と桁区切り表示
- **エラーメッセージ**: 必ず日本語で表示
- **更新予定表示**: ダッシュボードでは7日以内に更新日があるサブスクリプションを表示
- **トークンブラックリスト**: ログアウト時にサーバー側でトークンを無効化
- **APIドキュメント公開範囲**: `/docs`（Swagger UI）・`/redoc`・`/openapi.json` は開発環境（`APP_ENV=development`）のみ公開。本番環境では攻撃面を減らすため全て404を返す
- **CSP の条件付き緩和**: 開発環境の `/docs` 系パスのみ Swagger UI 動作のため `script-src/style-src` に `cdn.jsdelivr.net` と `'unsafe-inline'` を許可する緩和CSPを適用。本番環境・その他パスでは `default-src 'none'` を維持。本番で `/docs` 自体が無効化されるため、緩和CSPが攻撃経路になることはない

## 実装ロードマップ

プロジェクトは `docs/tasks.md` に定義された13チェックポイントの段階的計画に従う。`*` マークのタスクはMVP向けにはオプション。各フェーズは前のフェーズの成果物を基に構築。タスク4、10、13がチェックポイント（検証ゲート）。

## 参考ドキュメント

- `docs/requirements.md` — 全10要件カテゴリの受け入れ基準
- `docs/design.md` — コンポーネントインターフェース、データモデル、Pydanticスキーマ、エラーハンドリング戦略
- `docs/tasks.md` — 要件トレーサビリティ付きのステップバイステップ実装計画

## 開発ルール

- コード変更時は必ず理由を説明してから実施する
- 新しい概念（例: Alembic、JWT）を使う際は簡単に解説を入れる
- 日本語でコメント・ドキュメント・Docstringを書く
- design.md のデータモデル・API設計に従う
- Pydantic でバリデーション
- SQLAlchemy ORM でDB操作
- エラーメッセージは日本語
- SQLやDB操作の指示を出す際は、必ず実際のモデル定義（`backend/models/`配下）を確認してからクエリやコマンドを提示すること
- タスク完了時にPylanceの警告がないことを確認してからコミットすること

## Git運用ルール

- タスク完了ごとに git commit する
- コミットメッセージは日本語で、何を実装したか明確に書く
- コミットメッセージ形式: `feat: タスクX - 〇〇を実装`
- 大きなタスクは意味のある単位で分割してコミットする
- コミットメッセージに `Co-Authored-By:` 表記を含めない

## 学習ナレッジ

- 各作業毎に実行するコマンドや作業手順や使用している技術スタック全般を`docs/learning-notes.md` に追記する
- タスク番号と紐づけて記載する
- 記載内容:
  - 技術名と概要
  - なぜこの技術を選んだか
  - このコマンドは何のために使うのか
  - コードの構文
  - 基本的な使い方（コード例付き）
  - ハマりやすいポイント
  - 参考リンク