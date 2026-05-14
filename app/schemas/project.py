import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.language import LanguageCode
from app.models.project_member import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_language: LanguageCode


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    source_language: LanguageCode | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_language: str
    created_by: uuid.UUID | None
    created_at: datetime
    languages: list[LanguageCode] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def coerce_languages(cls, data):
        if isinstance(data, dict):
            return data
        # ORM object: convert ProjectLanguage rows to plain strings
        langs = getattr(data, "languages", None) or []
        return {
            "id": data.id,
            "name": data.name,
            "source_language": data.source_language,
            "created_by": data.created_by,
            "created_at": data.created_at,
            "languages": sorted(pl.language for pl in langs),
        }


class LanguageStats(BaseModel):
    language: str
    translated: int
    needs_review: int
    missing: int


class ProjectStats(BaseModel):
    total_strings: int
    languages: list[LanguageStats]


class LanguageAdd(BaseModel):
    language: LanguageCode


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
