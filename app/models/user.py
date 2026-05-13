import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GlobalRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    global_role: Mapped[GlobalRole] = mapped_column(Enum(GlobalRole), nullable=False, default=GlobalRole.user)
    recovery_word_hash: Mapped[str] = mapped_column(String, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    passkey_credentials: Mapped[list["PasskeyCredential"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    project_memberships: Mapped[list["ProjectMember"]] = relationship(  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[ProjectMember.user_id]",
    )
