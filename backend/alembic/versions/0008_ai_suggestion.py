"""add ai_suggestion to localizations

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("localizations", sa.Column("ai_suggestion", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("localizations", "ai_suggestion")
