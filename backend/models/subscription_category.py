"""
サブスクリプションカテゴリ列挙型

サブスクリプションの分類に使用する固定カテゴリ。
Python の enum.Enum と str を継承し、SQLAlchemy の PostgreSQL ENUM 型と対応する。
"""

import enum


class SubscriptionCategory(str, enum.Enum):
    """サブスクリプションのカテゴリ分類"""

    VIDEO_STREAMING = "動画配信"
    MUSIC = "音楽"
    GAMING = "ゲーム"
    OTHER = "その他"
