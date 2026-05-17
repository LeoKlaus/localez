import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, Response, status
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
from app.config import settings
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    PasskeyAuthBeginResponse,
    PasskeyAuthCompleteRequest,
    PasskeyCompleteRequest,
    PasskeyRegisterBeginResponse,
    RecoverRequest,
    RefreshRequest,
    RegisterCookieResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "USERNAME_TAKEN", "message": "Username already taken"})

    user, words, access_token, refresh_token = await auth_service.register_user(db, body.username, body.password)
    await db.commit()
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
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_json(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.authenticate_user(db, body.username, body.password, body.totp_code)
    if result == "TOTP_REQUIRED":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "TOTP_REQUIRED", "message": "TOTP code required"})
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"})
    _, access_token, refresh_token = result
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.rotate_refresh_token(db, body.refresh_token)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"})
    access_token, new_refresh = result
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    await db.commit()


# ---------------------------------------------------------------------------
# Cookie-based auth endpoints
# The refresh token is stored in an HttpOnly cookie rather than the response
# body, making it inaccessible to JavaScript and immune to XSS theft.
# ---------------------------------------------------------------------------

_COOKIE_NAME = "lz_refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86_400,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


@router.post("/register/cookie", response_model=RegisterCookieResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_cookie(request: Request, body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select as _select
    existing = await db.execute(_select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "USERNAME_TAKEN", "message": "Username already taken"})

    user, words, access_token, refresh_token = await auth_service.register_user(db, body.username, body.password)
    await db.commit()
    _set_refresh_cookie(response, refresh_token)
    return RegisterCookieResponse(access_token=access_token, recovery_words=words)


@router.post("/login/cookie", response_model=AccessTokenResponse)
@limiter.limit("10/minute")
async def login_cookie(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await auth_service.authenticate_user(db, body.username, body.password, body.totp_code)
    if result == "TOTP_REQUIRED":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "TOTP_REQUIRED", "message": "TOTP code required"})
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"})
    _, access_token, refresh_token = result
    await db.commit()
    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/refresh/cookie", response_model=AccessTokenResponse)
@limiter.limit("30/minute")
async def refresh_cookie(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    lz_refresh: str | None = Cookie(default=None),
):
    if not lz_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "MISSING_REFRESH_TOKEN", "message": "No refresh token cookie"})
    result = await auth_service.rotate_refresh_token(db, lz_refresh)
    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"})
    access_token, new_refresh = result
    await db.commit()
    _set_refresh_cookie(response, new_refresh)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout/cookie", status_code=status.HTTP_204_NO_CONTENT)
async def logout_cookie(
    response: Response,
    db: AsyncSession = Depends(get_db),
    lz_refresh: str | None = Cookie(default=None),
):
    if lz_refresh:
        await auth_service.revoke_refresh_token(db, lz_refresh)
        await db.commit()
    _clear_refresh_cookie(response)


@router.post("/passkey/authenticate/complete/cookie", response_model=AccessTokenResponse)
@limiter.limit("10/minute")
async def passkey_auth_complete_cookie(
    request: Request,
    body: PasskeyAuthCompleteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
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
        logger.warning("Passkey authentication failed: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "PASSKEY_AUTH_FAILED", "message": "Passkey authentication failed"})

    user = await db.get(User, cred.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "ACCOUNT_DISABLED", "message": "Account disabled"})

    access_token, refresh_token = await auth_service._issue_tokens(db, user)
    await db.commit()
    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/recover", response_model=TokenResponse)
@limiter.limit("5/minute")
async def recover(request: Request, body: RecoverRequest, db: AsyncSession = Depends(get_db)):
    result = await auth_service.recover_account(db, body.username, body.recovery_words, body.new_password)
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "RECOVERY_FAILED", "message": "Invalid username or recovery words"})
    access_token, refresh_token = result
    await db.commit()
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
        logger.warning("Passkey registration failed: %s", e)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "PASSKEY_REGISTRATION_FAILED", "message": "Passkey registration failed"})

    db.add(PasskeyCredential(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        aaguid=str(verified.aaguid) if verified.aaguid else None,
        name=body.name,
    ))
    await db.commit()
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
        logger.warning("Passkey authentication failed: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "PASSKEY_AUTH_FAILED", "message": "Passkey authentication failed"})

    user = await db.get(User, cred.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "ACCOUNT_DISABLED", "message": "Account disabled"})

    access_token, refresh_token = await auth_service._issue_tokens(db, user)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
