-- サブスクリプション管理アプリ DDL
-- design.md のデータモデルに基づくテーブル定義

-- カテゴリ列挙型
-- サブスクリプションの分類: 動画配信、音楽、ゲーム、その他
CREATE TYPE subscription_category AS ENUM (
    '動画配信',
    '音楽',
    'ゲーム',
    'その他'
);

-- ユーザーテーブル
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- サブスクリプションテーブル
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL,
    monthly_fee DECIMAL(10, 2) NOT NULL CHECK (monthly_fee > 0),
    category subscription_category NOT NULL,
    start_date DATE NOT NULL,
    next_renewal_date DATE NOT NULL,
    memo TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
-- ユーザーIDでの検索を高速化（サブスクリプション一覧取得で使用）
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
-- 更新予定のフィルタリングを高速化（7日以内の更新日検索で使用）
CREATE INDEX idx_subscriptions_next_renewal_date ON subscriptions(next_renewal_date);
-- アクティブなサブスクリプションのフィルタリング用
CREATE INDEX idx_subscriptions_is_active ON subscriptions(is_active);
