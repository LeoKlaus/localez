import uuid
from datetime import datetime

from pydantic import BaseModel


class ProposalCreate(BaseModel):
    proposed_value: str
    comment: str


class ProposalResponse(BaseModel):
    id: uuid.UUID
    localization_id: uuid.UUID
    proposed_value: str
    proposed_by: uuid.UUID | None
    proposed_at: datetime
    comment: str

    model_config = {"from_attributes": True}
