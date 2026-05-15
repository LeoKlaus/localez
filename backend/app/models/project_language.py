import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectLanguage(Base):
    __tablename__ = "project_languages"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(20), primary_key=True)

    project: Mapped["Project"] = relationship(back_populates="languages")  # noqa: F821
