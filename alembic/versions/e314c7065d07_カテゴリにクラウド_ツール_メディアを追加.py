"""カテゴリにクラウド・ツール・メディアを追加

Revision ID: e314c7065d07
Revises: 7f00a0d9e10f
Create Date: 2026-04-05 17:51:39.562496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e314c7065d07'
down_revision: Union[str, Sequence[str], None] = '7f00a0d9e10f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostgreSQL の ENUM 型に新しい値を追加する
    # ALTER TYPE は DDL トランザクション外で実行する必要があるため
    # execution_options(isolation_level="AUTOCOMMIT") を使用する
    op.execute("ALTER TYPE subscription_category ADD VALUE IF NOT EXISTS 'クラウド'")
    op.execute("ALTER TYPE subscription_category ADD VALUE IF NOT EXISTS 'ツール'")
    op.execute("ALTER TYPE subscription_category ADD VALUE IF NOT EXISTS 'メディア'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL では ENUM 値の削除はサポートされていないため、
    # ダウングレード時は手動対応が必要（または再作成）
    pass
