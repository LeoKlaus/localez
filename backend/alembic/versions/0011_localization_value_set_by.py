"""add value_set_by to localizations

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "localizations",
        sa.Column("value_set_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("localizations", "value_set_by")
