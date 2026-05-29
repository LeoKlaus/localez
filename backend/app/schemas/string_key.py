import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.language import LanguageCode
from app.models.localization import LocalizationState, VariationType


class LocalizationResponse(BaseModel):
    id: uuid.UUID
    language: LanguageCode
    variation_type: VariationType
    variation_key: str | None  # '' stored in DB is surfaced as None to clients

    @field_validator("variation_key", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: str) -> str | None:
        return None if v == "" else v
    state: LocalizationState
    value: str | None
    value_set_by: uuid.UUID | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalizationWithKeyResponse(LocalizationResponse):
    string_key_id: uuid.UUID
    key: str
    comment: str | None
    comment_auto_generated: bool
    source_value: str | None
    ai_suggestion: str | None


class StringKeyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    comment: str | None
    comment_auto_generated: bool
    should_translate: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocalizationValueSet(BaseModel):
    value: str


class LocalizationStateUpdate(BaseModel):
    state: LocalizationState


class StringKeyDetail(StringKeyResponse):
    localizations: list[LocalizationResponse] = []
