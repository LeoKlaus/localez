import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.language import LanguageCode
from app.models.localization import LocalizationState, VariationType


class LocalizationResponse(BaseModel):
    id: uuid.UUID
    language: LanguageCode
    variation_type: VariationType
    variation_key: str | None
    state: LocalizationState
    value: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class StringKeyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    comment: str | None
    should_translate: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StringKeyDetail(StringKeyResponse):
    localizations: list[LocalizationResponse] = []
