"""add token_type to project_tokens

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE tokentype AS ENUM ('import_token', 'export_token')")
    op.add_column(
        "project_tokens",
        sa.Column(
            "token_type",
            sa.Enum("import_token", "export_token", name="tokentype", create_type=False),
            nullable=False,
            server_default="import_token",
        ),
    )


def downgrade() -> None:
    op.drop_column("project_tokens", "token_type")
    op.execute("DROP TYPE tokentype")
