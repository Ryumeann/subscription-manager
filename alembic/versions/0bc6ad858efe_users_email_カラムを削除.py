"""users.email カラムを削除

Revision ID: 0bc6ad858efe
Revises: e314c7065d07
Create Date: 2026-05-10 16:05:59.135778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bc6ad858efe'
down_revision: Union[str, Sequence[str], None] = 'e314c7065d07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    users.email カラムと UNIQUE 制約を削除する。
    パスワードリセットや通知メール機能を実装しないため、当面メールは不要と判断。
    """
    # UNIQUE 制約を先に削除する（PostgreSQL では制約名が users_email_key になる）
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_column("users", "email")


def downgrade() -> None:
    """Downgrade schema.

    email カラムを復元する。既存データは失われているため、
    一旦 NULL 許可で追加し、後から手動で値を埋める想定。
    """
    op.add_column(
        "users",
        sa.Column("email", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint("users_email_key", "users", ["email"])
