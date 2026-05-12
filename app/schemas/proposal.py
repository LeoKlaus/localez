import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.translation_proposal import ProposalStatus


class ProposalCreate(BaseModel):
    proposed_value: str


class ProposalReview(BaseModel):
    reviewer_note: str | None = None


class ProposalResponse(BaseModel):
    id: uuid.UUID
    localization_id: uuid.UUID
    proposed_value: str
    proposed_by: uuid.UUID | None
    proposed_at: datetime
    status: ProposalStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    reviewer_note: str | None

    model_config = {"from_attributes": True}
