import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.language import LanguageCode
from app.models.project_member import ProjectRole
from app.models.project_token import TokenType


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_language: LanguageCode
    is_public: bool = False
    description: str | None = Field(default=None, max_length=10_000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    source_language: LanguageCode | None = None
    is_public: bool | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_language: str
    created_by: uuid.UUID | None
    created_at: datetime
    has_icon: bool
    is_public: bool
    description: str | None = None
    languages: list[LanguageCode] = []
    my_role: ProjectRole | None = None  # Current user's project role; None for global admins and non-members

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
            "is_public": data.is_public,
            "description": data.description,
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


class ProjectMemberCreate(BaseModel):
    username: str
    role: ProjectRole = ProjectRole.translator


class ProjectMemberUpdate(BaseModel):
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    username: str
    role: ProjectRole
    created_at: datetime


class ProjectTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    token_type: TokenType = TokenType.import_token


class ProjectTokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    token_type: TokenType
    created_by: uuid.UUID | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class ProjectTokenCreatedResponse(ProjectTokenResponse):
    token: str  # raw token, returned once on creation
