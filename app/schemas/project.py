import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.language import LanguageCode

_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_language: LanguageCode


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    source_language: LanguageCode | None = None
    accent_color: str | None = None

    @field_validator("accent_color")
    @classmethod
    def validate_hex(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_RE.match(v):
            raise ValueError("accent_color must be a 6-digit hex color, e.g. #FF5733")
        return v


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_language: str
    created_by: uuid.UUID | None
    created_at: datetime
    accent_color: str | None
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
            "accent_color": data.accent_color,
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
