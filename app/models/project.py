import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.project_language import ProjectLanguage


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_language: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[bytes | None] = mapped_column(LargeBinary(), nullable=True)

    languages: Mapped[list["ProjectLanguage"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    string_keys: Mapped[list["StringKey"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
