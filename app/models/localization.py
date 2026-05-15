import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VariationType(str, enum.Enum):
    none = "none"
    device = "device"
    plural = "plural"


class LocalizationState(str, enum.Enum):
    new = "new"
    needs_review = "needs_review"
    translated = "translated"


class Localization(Base):
    __tablename__ = "localizations"
    __table_args__ = (
        UniqueConstraint("string_key_id", "language", "variation_type", "variation_key"),
        Index("ix_localizations_string_key_id", "string_key_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    string_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("string_keys.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    variation_type: Mapped[VariationType] = mapped_column(Enum(VariationType), nullable=False, default=VariationType.none)
    variation_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[LocalizationState] = mapped_column(Enum(LocalizationState), nullable=False, default=LocalizationState.new)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    string_key: Mapped["StringKey"] = relationship(back_populates="localizations")  # noqa: F821
    proposals: Mapped[list["TranslationProposal"]] = relationship(  # noqa: F821
        back_populates="localization", cascade="all, delete-orphan"
    )
