"""make variation_key non-nullable with empty string sentinel

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE localizations SET variation_key = '' WHERE variation_key IS NULL")
    op.alter_column("localizations", "variation_key", nullable=False, server_default="")


def downgrade() -> None:
    op.alter_column("localizations", "variation_key", nullable=True, server_default=None)
    op.execute("UPDATE localizations SET variation_key = NULL WHERE variation_key = ''")
