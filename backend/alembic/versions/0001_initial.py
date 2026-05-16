"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("global_role", sa.Enum("user", "admin", name="globalrole"), nullable=False, server_default="user"),
        sa.Column("recovery_word_hash", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("totp_secret", sa.Text, nullable=True),
    )

    op.create_table(
        "passkey_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("sign_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("aaguid", sa.String, nullable=True),
        sa.Column("name", sa.String(100), nullable=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String, nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_language", sa.String(20), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("icon", sa.LargeBinary, nullable=True),
    )

    op.create_table(
        "project_languages",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("language", sa.String(20), primary_key=True),
    )

    op.create_table(
        "string_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("should_translate", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "key"),
    )

    op.create_table(
        "localizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("string_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("string_keys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.Text, nullable=False),
        sa.Column("variation_type", sa.Enum("none", "device", "plural", name="variationtype"), nullable=False, server_default="none"),
        sa.Column("variation_key", sa.Text, nullable=False, server_default=""),
        sa.Column("state", sa.Enum("new", "needs_review", "translated", name="localizationstate"), nullable=False, server_default="new"),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("value_set_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ai_suggestion", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("string_key_id", "language", "variation_type", "variation_key"),
    )
    op.create_index("ix_localizations_string_key_id", "localizations", ["string_key_id"])

    op.create_table(
        "translation_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("localization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("localizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_value", sa.Text, nullable=False),
        sa.Column("proposed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("comment", sa.Text, nullable=False),
    )
    op.create_index("ix_proposals_localization_id", "translation_proposals", ["localization_id"])


def downgrade() -> None:
    op.drop_index("ix_proposals_localization_id", table_name="translation_proposals")
    op.drop_table("translation_proposals")
    op.drop_index("ix_localizations_string_key_id", table_name="localizations")
    op.drop_table("localizations")
    op.drop_table("string_keys")
    op.drop_table("project_languages")
    op.drop_table("projects")
    op.drop_table("refresh_tokens")
    op.drop_table("passkey_credentials")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS localizationstate")
    op.execute("DROP TYPE IF EXISTS variationtype")
    op.execute("DROP TYPE IF EXISTS globalrole")
