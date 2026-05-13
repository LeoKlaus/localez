import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import GlobalRole


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    global_role: GlobalRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(UserResponse):
    totp_enabled: bool
    passkeys_configured: bool


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UpdateRoleRequest(BaseModel):
    global_role: GlobalRole


class TotpSetupResponse(BaseModel):
    secret: str
    uri: str


class TotpCodeRequest(BaseModel):
    code: str


class TotpVerifyRequest(BaseModel):
    secret: str
    code: str
