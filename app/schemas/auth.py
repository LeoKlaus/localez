from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    recovery_words: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RecoverRequest(BaseModel):
    username: str
    recovery_words: list[str] = Field(min_length=12, max_length=12)
    new_password: str = Field(min_length=8)


class PasskeyRegisterBeginResponse(BaseModel):
    options: dict
    challenge_token: str


class PasskeyCompleteRequest(BaseModel):
    credential: dict
    challenge_token: str
    name: str | None = None


class PasskeyAuthBeginResponse(BaseModel):
    options: dict
    challenge_token: str


class PasskeyAuthCompleteRequest(BaseModel):
    credential: dict
    challenge_token: str
