"""add contributor settings to users

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("show_as_contributor", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("attribution_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "attribution_name")
    op.drop_column("users", "show_as_contributor")
