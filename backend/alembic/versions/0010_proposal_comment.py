"""add comment to translation proposals

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("translation_proposals", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    op.alter_column("translation_proposals", "comment", server_default=None)


def downgrade() -> None:
    op.drop_column("translation_proposals", "comment")
