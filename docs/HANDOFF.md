# 引き継ぎドキュメント（HANDOFF.md）

このファイルは、新しい Claude Code セッションが**即座にプロジェクトの全体像を把握して作業を継続できる**ように、これまでの実装内容・決定事項・残タスクを一元化したものです。

最終更新: 2026-06-07

---

## 0. 最初に読むべきファイル（優先順）

1. **このファイル（HANDOFF.md）** — 全体像と残タスク
2. **CLAUDE.md** — 開発ルール・本番運用・設計上の決定事項
3. **docs/tasks.md** — タスクのチェックリスト
4. **docs/learning-notes.md** — 各タスクで得た技術知見
5. `docs/design.md` / `docs/requirements.md` — 要件・設計

---

## 1. プロジェクト概要

サブスクリプション管理 Web アプリケーション。Netflix / Spotify などの月額サブスクを一元管理する。

- **言語/フレームワーク**: Python 3.10、FastAPI、Streamlit、SQLAlchemy 2.x、Pydantic v2
- **DB**: PostgreSQL（開発: Docker / 本番: Supabase）
- **認証**: JWT（アクセス24h + リフレッシュ30d）+ bcrypt
- **パッケージ管理**: Poetry
- **テスト**: pytest（303件パス・カバレッジ 91%）
- **UI**: 日本語、通貨は日本円（JPY、`Decimal(10,2)`）

### アーキテクチャ

```
ブラウザ
  ↓
Streamlit（:8501、views/login,dashboard,subscriptions）
  ↓ HTTP
FastAPI（:8000、routers/auth,subscriptions,dashboard）
  ↓
SQLAlchemy ORM → PostgreSQL
```

### ディレクトリ構成

```
backend/
  models/         # SQLAlchemy ORM（User、Subscription、SubscriptionCategory）
  routers/        # FastAPIエンドポイント（auth, subscriptions, dashboard）
  services/       # ビジネスロジック層
  schemas/        # Pydantic（リクエスト/レスポンス）
  middleware/     # SecurityHeadersMiddleware、CSRFProtectionMiddleware
  tests/          # pytestテスト（207件）
frontend/
  app.py          # Streamlit エントリポイント
  api_client.py   # FastAPIへのHTTPクライアント
  views/          # 各画面（login, dashboard, subscriptions）← 旧 pages/
  tests/          # フロント単体テスト（39件、views/ロジックのみ）
alembic/          # DBマイグレーション
scripts/          # 本番DB接続ヘルパー（load_prod_env.sh / unload_prod_env.sh）
docs/             # 要件・設計・学習ノート
```

⚠️ **`frontend/pages/` ではなく `frontend/views/`** にリネーム済み。Streamlit が `pages/` ディレクトリを自動マルチページ機能の対象とするため。

---

## 2. 進捗サマリ

### タスク完了状況（docs/tasks.md より）

| 番号 | タスク | 状態 |
|------|--------|------|
| 1〜3 | プロジェクト基盤・モデル・認証システム | ✅ |
| 4 | チェックポイント（認証・データモデル） | ✅ |
| 5 | サブスクリプション管理API | ✅ |
| 6 | ダッシュボードサービス | ✅ |
| 7 | 通知システム | ✅ |
| 8 | ログ・エラーハンドリング | ✅ |
| 9 | セキュリティミドルウェア | ✅ |
| 10 | チェックポイント（バックエンドAPI完成） | ✅ |
| 11 | Streamlitフロントエンド | ✅ |
| 12.1 | フロント・バックエンド統合 | ✅ |
| 12.2 | 統合テスト（20件追加） | ✅ |
| 12.3 | Dockerファイル + Supabase構築 | ✅（AWSインフラは未） |
| 13 | 最終チェックポイント | ✅ |

### MVP として完了している機能

- **認証**: 新規登録 / ログイン / ログアウト / トークン更新（リフレッシュローテーション + ブラックリスト）
- **サブスク管理**: 一覧・追加・編集・論理削除、サービス名プルダウン（54サービス）+ カテゴリ自動連動
- **ダッシュボード**: 月間総支出、カテゴリ別円グラフ、月別推移、7日以内の更新予定
- **通知**: 更新日チェック、自動次回更新日計算
- **セキュリティ**: CORS、CSRF、CSP、HSTS、X-Frame-Options ほか
- **ログ**: 構造化JSON、CloudWatch Logs 連携前提
- **エラーハンドラ**: 統一フォーマット（日本語メッセージ + UUID request_id）
- **API ドキュメント**: 開発環境のみ `/docs` `/redoc` `/openapi.json` 公開
- **レスポンシブUI**: max-width 768px でカラム縦積み（スマホ対応）

---

## 3. 重要な技術的決定事項

このセクションは「なぜそうなっているか」を新しいセッションが理解できるように残します。

### 3.1 User.email を削除（重要）

**経緯**: 当初 email カラムを持っていたが、パスワードリセット / メール通知機能を実装しない方針のため不要と判断。

**現状**:
- `User` モデルから `email` フィールド削除済み
- DBマイグレーション `0bc6ad858efe_users_email_カラムを削除.py` 適用済み
- ローカルDB・Supabase 両方とも適用済み
- `RegisterRequest` から email 削除、`pydantic[email]` 依存も削除

**新規登録時に必要なフィールド**: `username` + `password` のみ

### 3.2 サブスクリプションカテゴリ（7種類）

| カテゴリ | サービス例 |
|---------|-----------|
| 動画配信 | Netflix, Amazon Prime Video, Disney+, Hulu, U-NEXT, YouTube Premium 等 |
| 音楽 | Spotify, Apple Music, Amazon Music Unlimited, YouTube Music 等 |
| ゲーム | Nintendo Switch Online, PlayStation Plus, Xbox Game Pass, Steam 等 |
| クラウド | iCloud+, Google One, Dropbox, OneDrive, Box |
| ツール | Adobe CC, Microsoft 365, Notion, Figma, ChatGPT Plus, GitHub Copilot 等 |
| メディア | Kindle Unlimited, コミックシーモア, NewsPicks, 日経電子版 等 |
| その他 | 上記に該当しないもの |

→ `frontend/views/subscriptions.py:SERVICE_CATEGORY_MAP` でサービス名から自動推定する。

### 3.3 APIドキュメント公開範囲（環境別）

| 環境 | `/docs` `/redoc` `/openapi.json` | CSP |
|------|---------------------------------|-----|
| development | 公開（200） | `/docs` 系のみ緩和 CSP（jsdelivr + unsafe-inline 許可） |
| production | 全て 404 | `default-src 'none'`（厳格） |

実装場所:
- `backend/main.py`: 環境変数 `APP_ENV` で `docs_url=None` を分岐
- `backend/middleware/security.py:SecurityHeadersMiddleware`: パスごとに CSP 切り替え

### 3.4 認証フローの詳細

- **JWT 署名**: HS256
- **アクセストークン**: 24時間
- **リフレッシュトークン**: 30日
- **リフレッシュ時**: 新しいペアを発行（トークンローテーション）+ 古いリフレッシュトークンをブラックリスト追加
- **ログアウト**: アクセストークンをブラックリスト追加
- **ブラックリスト保存**: インメモリ `set()`（再起動でクリア）⚠️ 本番ではRedis/DB化推奨
- **新規登録成功時**: 自動でトークン発行して即ログイン状態へ

### 3.5 パスワード要件

8文字以上、**大文字英字・小文字英字・数字を各1文字以上**。`RegisterRequest._validate_password_complexity` で検証。

### 3.6 ユーザー名要件

3〜50文字、半角英数字・アンダースコア（`_`）・ハイフン（`-`）のみ。

### 3.7 グローバルエラーハンドラの ctx 除外

Pydantic の `RequestValidationError.errors()` は `ctx` フィールドに元の `ValueError` オブジェクトを含むため、そのままだとJSON シリアライズに失敗する。

→ `backend/error_handlers.py:_validation_exception_handler` で `ctx` と `input` を除外したコピーを返す。

### 3.8 boto3 を main 依存から削除

アプリ本体で `import boto3` していないため、main から削除。dev-dep の `moto` が依存しているので開発時は自動的にインストールされる。本番イメージサイズ削減効果あり。

### 3.9 frontend/pages/ → views/ にリネーム

Streamlit は `pages/` という名前のディレクトリを自動マルチページ機能の対象にする。意図しないナビゲーション項目がサイドバーに自動追加されたため、`views/` にリネームして無効化。

### 3.10 サイドバーから自動マルチページが見えなくなった理由

これは `views/` リネームで解決済みだが、新しいセッションが「なぜ pages じゃないの？」と疑問に思った場合のために記録。

### 3.11 Supabase の Session pooler 使用

WSL2 環境では IPv6 通信ができないため、Supabase の Direct connection（IPv6のみ）は使えない。**Session pooler（IPv4対応）** を使う必要がある。

接続文字列の形式: `postgresql://postgres.<project_ref>:<password>@aws-1-<region>.pooler.supabase.com:5432/postgres`

### 3.12 レスポンシブCSS

`frontend/app.py` に `@media (max-width: 768px)` を定義済み。`st.columns()` を縦積みに、見出しサイズを縮小、メトリクスを小型化。

---

## 4. 本番環境の運用

### 4.1 本番DB（Supabase）

- プロジェクト名: `subscription-manager`
- リージョン: ap-northeast-1（東京）
- 接続方式: Session pooler（IPv4）
- 無料枠で運用中

### 4.2 ロール分離（4種）

| ロール | 権限 | 用途 |
|--------|------|------|
| `subscription_readonly` | SELECT のみ | データ閲覧・調査 |
| `subscription_app` | CRUD のみ、DDL不可 | アプリ実行（ECS Fargate） |
| `subscription_owner` | DDL + DML | Alembic マイグレーション |
| `postgres` | スーパーユーザー | **緊急時のみ**（既存テーブル所有権変更等） |

### 4.3 SSM Parameter Store（AWS）

接続文字列を SecureString（KMS 暗号化）で保管。

```
/subscription-app/prod/database-url-readonly
/subscription-app/prod/database-url-app
/subscription-app/prod/database-url-owner
/subscription-app/prod/database-url-postgres   # 緊急時用
```

AWS CLI プロファイル: `subscription-app`（IAM ユーザー `subscription-app-admin`、リージョン `ap-northeast-1`）

### 4.4 本番DB接続の手順（隔離ターミナル）

```bash
# 1. AI が動いていない別の隔離ターミナルを開く
cd ~/projects/subscription-manager

# 2. ロールを指定してロード
source ./scripts/load_prod_env.sh readonly    # 閲覧
source ./scripts/load_prod_env.sh app         # アプリ実行
source ./scripts/load_prod_env.sh owner       # マイグレーション

# 緊急時のみ（ALLOW_POSTGRES=1 必須）
ALLOW_POSTGRES=1 source ./scripts/load_prod_env.sh postgres

# 3. 作業
poetry run alembic upgrade head      # owner
poetry run uvicorn backend.main:app   # app
poetry run python -c "..."            # readonly

# 4. 作業終了後、必ずクリア
source ./scripts/unload_prod_env.sh
```

### 4.5 隔離運用の絶対ルール

1. **AI コーディング支援ツールが動いているターミナルで本番接続文字列を扱わない**
2. **本番接続情報を `.env` に書かない**
3. **作業終了時は必ず `unload_prod_env.sh` を実行**
4. **`.env*`、AWS キー、JWT シークレット実値、SSM 取得文字列を Git にコミットしない**

---

## 5. ローカル開発の起動方法

### 前提

- Docker Desktop（WSL2連携）起動済み
- Poetry インストール済み
- `.env` がローカルDB設定になっている（`DATABASE_URL=postgresql://postgres:postgres@localhost:5432/subscription_manager`）

### 起動

```bash
# 1. PostgreSQL（Docker）起動
docker compose up -d

# 2. 依存インストール
poetry install

# 3. マイグレーション適用（初回 or 変更時）
poetry run alembic upgrade head

# 4. バックエンド起動（ターミナル1）
poetry run uvicorn backend.main:app --reload

# 5. フロントエンド起動（ターミナル2）
poetry run streamlit run frontend/app.py
```

### アクセス先

| 用途 | URL |
|------|-----|
| Streamlit フロント | http://localhost:8501 |
| FastAPI | http://localhost:8000 |
| Swagger UI（開発のみ） | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| ヘルスチェック | http://localhost:8000/health |

### 既存ローカルアカウント

| ユーザー名 | パスワード |
|------------|-----------|
| `admin` | `admin1234` |
| `user` | `user1234` |

（ローカルDBのみ。Supabase 側は空）

---

## 6. テストの実行

```bash
poetry run pytest                                 # 全テスト
poetry run pytest backend/tests/test_auth.py      # 単一ファイル
poetry run pytest -k "test_register"              # 名前で絞り込み
poetry run pytest --cov=backend --cov=frontend    # カバレッジ
```

### 現状

- **303件パス**
- バックエンドカバレッジ: 96%以上
- フロントエンドカバレッジ: views/ は低い（Streamlit UI はテスト困難）
- API クライアント・定数・マッピングは100%

---

## 7. Docker

### イメージビルド

```bash
docker build -f Dockerfile.backend -t subscription-manager-backend .
docker build -f Dockerfile.frontend -t subscription-manager-frontend .
```

### WSL2 + Docker Desktop の認証ヘルパー問題

`~/.docker/config.json` が `"credsStore": "desktop.exe"` のままだとビルドが `exec format error` で失敗する。**publicイメージのpullなら認証不要**なので、`config.json` を `{}` に置き換えれば通る。作業後に元に戻す。

### 現在のイメージサイズ

- backend: 約 482MB
- frontend: 約 476MB

### docker-compose

- `docker-compose.yml`: 開発用（DBコンテナのみ）
- `docker-compose.prod.yml`: 本番構成テスト用（backend + frontend + DB の3コンテナ）

---

## 8. 残タスク

### A. AWS インフラ構築（タスク12.3 の残り）

**ユーザーの方針**: **構成D（必要なときだけ ECS タスクを起動）** で月3,000円程度を目指す。

| ステップ | 内容 | コメント |
|---------|------|----------|
| 1 | ECR リポジトリ作成（backend / frontend 2つ） | マネコンか CLI |
| 2 | Dockerイメージビルド & ECRへ push | プロファイル `subscription-app` を使う |
| 3 | VPC / サブネット / セキュリティグループ確認 | 既存 default VPC でも可 |
| 4 | CloudWatch Logs ロググループ作成 | `/ecs/subscription-app/backend` 等 |
| 5 | ECS Fargate クラスタ作成 | |
| 6 | ECS タスク定義 | SSM経由で `DATABASE_URL` 注入、`APP_ENV=production`、`SECRET_KEY` も SSM 経由 |
| 7 | ALB + ターゲットグループ + リスナー | |
| 8 | ECS サービス（Desired count = 0 で待機） | 使うとき 1 に変更 |
| 9 | （任意）Route 53 + ACM でカスタムドメイン + HTTPS | |

### B. AWS構築中に対応が必要なコード調整

| 項目 | 対象ファイル |
|------|------------|
| 本番ドメインを CORS 許可に追加 | `backend/config.py:cors_allowed_origins` |
| 本番ドメインを CSRF 許可に追加 | 同上（CSRFProtectionMiddleware が `cors_allowed_origins` を参照） |
| Streamlit→FastAPI接続先の環境変数化 | `frontend/api_client.py:API_BASE_URL` を `os.environ.get("API_BASE_URL", ...)` に |
| Streamlit のセッション扱い | 必要に応じて Streamlit のクッキー設定（HTTPS化後） |

### C. 任意の今後の改善（時間があれば）

- トークンブラックリストを Redis または DB テーブル化（現状インメモリ）
- リフレッシュトークン管理を Redis（インスタンス数が増えるとき必須）
- パスワードリセット機能（メール送信が必要 → 機能追加時に email カラム復活）
- ユーザーごとのサブスクリプション数上限などのレート制限
- E2Eテスト（Playwright等）
- GitHub Actions で CI（pytest 自動実行）

---

## 9. 開発・コミットのお作法

### コミットメッセージ

- 日本語で書く
- `feat: タスクX - 〇〇を実装` 形式（または `fix:` `docs:` `chore:` `refactor:` `test:`）
- `Co-Authored-By:` 表記は**含めない**

### 開発の流れ

1. コード変更時は**理由を説明してから**実施する
2. 新しい概念（Alembic、JWT 等）を使う際は**簡単な解説**を入れる
3. SQL/DB操作の指示前に必ず `backend/models/` を確認する
4. タスク完了時に Pylance の警告がないことを確認してからコミット
5. タスク終了時に `docs/learning-notes.md` へ追記（技術名・選定理由・コマンドの目的・コード例・ハマりやすいポイント）
6. **コミットは明示指示があったときのみ**作成する

### よく使うコマンド

```bash
poetry install
poetry run uvicorn backend.main:app --reload
poetry run streamlit run frontend/app.py
poetry run pytest
poetry run pytest --cov
poetry run alembic upgrade head
poetry run alembic revision -m "説明"
docker compose up -d
docker compose down
```

---

## 10. ブランチとリモートの状態

- 現在ブランチ: `feature/task1-project-foundation`
- リモート: `origin/feature/task1-project-foundation` と同期済み（最終コミット `5628ed2`）
- master へのマージ: PR #1 はマージ済み。それ以降の機能は今のブランチに溜まっている

### 直近のコミット履歴

```
5628ed2 docs: タスク13 - 最終チェックポイント完了に伴うドキュメント更新
c24e499 feat: フロントエンドUI改善（スマホ対応・自動マルチページ無効化）
1d4ca19 feat: 新規ユーザー登録機能を追加し、不要なemailフィールドを削除
b0e9204 feat: load_prod_env.sh に postgres ロール(緊急時用)を追加
2e0a2d2 feat: SSM経由で本番DB接続を取得するヘルパースクリプトを追加
d115908 chore: .gitignoreに環境変数関連ファイルを追加
a2a4053 feat: APIドキュメントの公開を開発環境限定にしCSPを環境別に分岐
2911097 chore: 不要なAWS認証情報とboto3依存を削除
17009a7 feat: タスク12.3 - Dockerファイルとデプロイ設定を作成
```

---

## 11. AWSコスト見積もり（参考）

東京リージョン、Supabase 無料枠継続、150円/USD換算。

| 構成 | 月額目安 | 説明 |
|------|---------|------|
| A. 標準（24h稼働） | 約 4,500〜5,000円 | ECS Fargate + ALB + CloudWatch |
| B. 平日日中のみ | 約 3,500円 | ECS は時間制限、ALB は固定費 |
| C. 超最小（ALBなし） | 約 1,000〜1,500円 | 運用が複雑、非推奨 |
| **D. 必要時のみ起動** | **約 3,000円〜（待機時）** | ECS Desired count = 0 で待機、使う時だけ 1 に |

ユーザー方針: **構成D**

### 無料枠を活用すると（最初の12ヶ月）

ALB 750h/月、CloudWatch 5GB等が無料で、**初年度は月1,500〜2,500円程度**に収まる見込み。

---

## 12. 次のセッションが最初にやるべきこと

1. **このファイル（HANDOFF.md）と CLAUDE.md を読む**
2. `git status` と `git log --oneline -10` で現状確認
3. **AWS の作業を CLI で進めるかマネコンで進めるかをユーザーに確認**
4. AWS CLI 動作確認: `aws sts get-caller-identity --profile subscription-app`
5. ECR リポジトリ作成から開始

### 注意事項

- **本番接続文字列は絶対にこのターミナルで扱わない**（隔離ターミナル運用）
- AWS 構築中、CORS/CSRF の追加調整が必要になったら `backend/config.py:cors_allowed_origins` を更新
- Docker の credsStore 問題が出たら本ファイルの「7. Docker」セクション参照
- 本番環境変数として `APP_ENV=production` を必ず設定（`/docs` 非公開のため）

---

## 13. 関連ドキュメント参照

- **CLAUDE.md** … 開発ルール・本番運用・設計上の決定事項
- **README.md** … プロジェクト概要・起動方法
- **docs/requirements.md** … 全10要件カテゴリの受け入れ基準
- **docs/design.md** … コンポーネントインターフェース・データモデル・エラーハンドリング戦略
- **docs/tasks.md** … タスクのチェックリスト
- **docs/learning-notes.md** … 各タスクの技術知見・コマンド・ハマりポイント
- **scripts/load_prod_env.sh** … 本番DB接続ヘルパー
- **scripts/unload_prod_env.sh** … 環境変数クリア

---

以上。新しいセッションはこのファイルを読めば、即座に作業を継続できる状態です。
