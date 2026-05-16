import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.localization import Localization


class TranslationProposal(Base):
    __tablename__ = "translation_proposals"
    __table_args__ = (Index("ix_proposals_localization_id", "localization_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    localization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("localizations.id", ondelete="CASCADE"), nullable=False)
    proposed_value: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    localization: Mapped["Localization"] = relationship(back_populates="proposals")  # noqa: F821
