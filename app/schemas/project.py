import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.project_member import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_language: str = Field(min_length=2, max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    source_language: str | None = Field(default=None, min_length=2, max_length=20)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_language: str
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    project_role: ProjectRole


class MemberUpdate(BaseModel):
    project_role: ProjectRole


class MemberResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    project_role: ProjectRole
    granted_by: uuid.UUID | None
    granted_at: datetime

    model_config = {"from_attributes": True}
