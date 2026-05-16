from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.passkey import (
    get_authentication_options,
    get_registration_options,
    verify_authentication,
    verify_registration,
)
from app.core.security import create_webauthn_challenge_token, decode_webauthn_challenge_token
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.passkey import PasskeyCredential
from app.models.user import User
from app.schemas.auth import (
    PasskeyAuthBeginResponse,
    PasskeyAuthCompleteRequest,
    PasskeyCompleteRequest,
    PasskeyRegisterBeginResponse,
    RecoverRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "USERNAME_TAKEN", "message": "Username already taken"})

    user, words, access_token, refresh_token = await auth_service.register_user(db, body.username, body.password)
    return RegisterResponse(access_token=access_token, refresh_token=refresh_token, recovery_words=words)


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    totp_code: Annotated[Optional[str], Form()] = None,
    db: AsyncSession = Depends(get_db),
):
    result = await auth_service.authenticate_user(db, form.username.lower(), form.password, totp_code)
    if result == "TOTP_REQUIRED":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "TOTP_REQUIRED", "message": "TOTP code required"})
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"})
    _, access_token, refresh_token = result
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.rotate_refresh_token(db, body.refresh_token)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"})
    access_token, new_refresh = result
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(db, body.refresh_token)


@router.post("/recover", response_model=TokenResponse)
@limiter.limit("5/minute")
async def recover(request: Request, body: RecoverRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.recover_account(db, body.username, body.recovery_words, body.new_password)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "RECOVERY_FAILED", "message": "Invalid username or recovery words"})
    access_token, refresh_token = result
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/passkey/register/begin", response_model=PasskeyRegisterBeginResponse)
@limiter.limit("10/minute")
async def passkey_register_begin(
    request: Request,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PasskeyCredential).where(PasskeyCredential.user_id == user.id))
    existing_ids = [c.credential_id for c in result.scalars()]

    options = get_registration_options(
        user_id=user.id.bytes,
        username=user.username,
        existing_credential_ids=existing_ids,
    )
    import webauthn, json
    options_dict = json.loads(webauthn.options_to_json(options))
    challenge_token = create_webauthn_challenge_token(options.challenge)
    return PasskeyRegisterBeginResponse(options=options_dict, challenge_token=challenge_token)


@router.post("/passkey/register/complete", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def passkey_register_complete(
    request: Request,
    body: PasskeyCompleteRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        challenge = decode_webauthn_challenge_token(body.challenge_token)
        verified = verify_registration(body.credential, challenge)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "PASSKEY_REGISTRATION_FAILED", "message": str(e)})

    db.add(PasskeyCredential(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        aaguid=str(verified.aaguid) if verified.aaguid else None,
        name=body.name,
    ))
    return {"message": "Passkey registered"}


@router.post("/passkey/authenticate/begin", response_model=PasskeyAuthBeginResponse)
@limiter.limit("10/minute")
async def passkey_auth_begin(request: Request, db: AsyncSession = Depends(get_db)):
    options = get_authentication_options()
    import webauthn, json
    options_dict = json.loads(webauthn.options_to_json(options))
    challenge_token = create_webauthn_challenge_token(options.challenge)
    return PasskeyAuthBeginResponse(options=options_dict, challenge_token=challenge_token)


@router.post("/passkey/authenticate/complete", response_model=TokenResponse)
@limiter.limit("10/minute")
async def passkey_auth_complete(request: Request, body: PasskeyAuthCompleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        challenge = decode_webauthn_challenge_token(body.challenge_token)
        import base64
        raw_id_str = body.credential.get("rawId", "")
        raw_cred_id = base64.urlsafe_b64decode(raw_id_str + "==")
        result = await db.execute(select(PasskeyCredential).where(PasskeyCredential.credential_id == raw_cred_id))
        cred = result.scalar_one_or_none()
        if cred is None:
            raise ValueError("Credential not found")

        verified = verify_authentication(
            credential=body.credential,
            expected_challenge=challenge,
            stored_public_key=cred.public_key,
            stored_sign_count=cred.sign_count,
        )
        cred.sign_count = verified.new_sign_count
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "PASSKEY_AUTH_FAILED", "message": str(e)})

    user = await db.get(User, cred.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "ACCOUNT_DISABLED", "message": "Account disabled"})

    access_token, refresh_token = await auth_service._issue_tokens(db, user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
