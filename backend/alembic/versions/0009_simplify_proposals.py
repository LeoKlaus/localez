"""simplify translation proposals — drop status and review columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_proposals_localization_status", table_name="translation_proposals")
    op.drop_column("translation_proposals", "status")
    op.drop_column("translation_proposals", "reviewed_by")
    op.drop_column("translation_proposals", "reviewed_at")
    op.drop_column("translation_proposals", "reviewer_note")
    op.execute("DROP TYPE IF EXISTS proposalstatus")
    op.create_index("ix_proposals_localization_id", "translation_proposals", ["localization_id"])


def downgrade() -> None:
    op.drop_index("ix_proposals_localization_id", table_name="translation_proposals")
    op.execute("CREATE TYPE proposalstatus AS ENUM ('pending', 'accepted', 'rejected')")
    op.add_column("translation_proposals", sa.Column("status", sa.Enum("pending", "accepted", "rejected", name="proposalstatus"), nullable=False, server_default="pending"))
    op.add_column("translation_proposals", sa.Column("reviewer_note", sa.Text(), nullable=True))
    op.add_column("translation_proposals", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("translation_proposals", sa.Column("reviewed_by", sa.UUID(), nullable=True))
    op.create_index("ix_proposals_localization_status", "translation_proposals", ["localization_id", "status"])
