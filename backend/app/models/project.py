import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.project_language import ProjectLanguage

from app.models.project_member import ProjectMember
from app.models.project_token import ProjectToken
from app.models.string_key import StringKey


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_language: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    icon: Mapped[bytes | None] = mapped_column(LargeBinary(), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    languages: Mapped[list["ProjectLanguage"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    string_keys: Mapped[list["StringKey"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    tokens: Mapped[list["ProjectToken"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
    members: Mapped[list["ProjectMember"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan"
    )
