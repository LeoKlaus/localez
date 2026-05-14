"""drop project_role from project_members

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("project_members", "project_role")
    op.execute("DROP TYPE IF EXISTS projectrole")


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'projectrole') THEN
                CREATE TYPE projectrole AS ENUM ('guest', 'translator', 'reviewer');
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE project_members ADD COLUMN IF NOT EXISTS project_role projectrole")
    op.execute("UPDATE project_members SET project_role = 'guest'")
    op.execute("ALTER TABLE project_members ALTER COLUMN project_role SET NOT NULL")
