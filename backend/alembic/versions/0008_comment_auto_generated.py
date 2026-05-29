"""add comment_auto_generated to string_keys

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-29
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None
 

def upgrade() -> None:
    op.add_column(
        "string_keys",
        sa.Column(
            "comment_auto_generated",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("string_keys", "comment_auto_generated")
