import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.language import LanguageCode


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
    has_icon: bool
    languages: list[LanguageCode] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def coerce_languages(cls, data):
        if isinstance(data, dict):
            return data
        langs = getattr(data, "languages", None) or []
        return {
            "id": data.id,
            "name": data.name,
            "source_language": data.source_language,
            "created_by": data.created_by,
            "created_at": data.created_at,
            "has_icon": data.icon is not None,
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


class PrefillResponse(BaseModel):
    filled: int
    skipped: int


class BackTranslateResponse(BaseModel):
    text: str


class ProjectTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProjectTokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_by: uuid.UUID | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ProjectTokenCreatedResponse(ProjectTokenResponse):
    token: str  # raw token, returned once on creation
