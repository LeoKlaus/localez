"""add accent_color and icon to projects

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("accent_color", sa.String(7), nullable=True))
    op.add_column("projects", sa.Column("icon", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "icon")
    op.drop_column("projects", "accent_color")
