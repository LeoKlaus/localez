import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.security import verify_password, hash_password
from app.core.totp import generate_totp_secret, get_totp_uri, verify_totp
from app.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.models.user import User
from app.models.passkey import PasskeyCredential
from app.schemas.user import MeResponse, TotpCodeRequest, TotpSetupResponse, TotpVerifyRequest, UpdateContributorSettingsRequest, UpdatePasswordRequest, UpdateRoleRequest, UserResponse

router = APIRouter()

MAX_LIMIT = 200


@router.get("/me", response_model=MeResponse)
async def get_me(user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    passkey_count = await db.scalar(select(func.count()).select_from(PasskeyCredential).where(PasskeyCredential.user_id == user.id))
    return MeResponse(
        **UserResponse.model_validate(user).model_dump(),
        totp_enabled=user.totp_secret is not None,
        passkeys_configured=passkey_count > 0,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(user)
    await db.commit()


@router.patch("/me", response_model=UserResponse)
async def update_password(
    body: UpdatePasswordRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "WRONG_PASSWORD", "message": "Current password is incorrect"})
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return user


@router.patch("/me/contributor", response_model=UserResponse)
async def update_contributor_settings(
    body: UpdateContributorSettingsRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    user.show_as_contributor = body.show_as_contributor
    user.attribution_name = body.attribution_name if body.show_as_contributor else None
    await db.commit()
    return user


@router.get("", response_model=list[UserResponse])
async def list_users(
    offset: int = 0,
    limit: int = 50,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    total = await db.scalar(select(func.count()).select_from(User))
    result = await db.execute(select(User).offset(offset).limit(limit))
    users = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "USER_NOT_FOUND", "message": "User not found"})
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "USER_NOT_FOUND", "message": "User not found"})
    user.global_role = body.global_role
    await db.commit()
    return user


@router.post("/me/totp/setup", response_model=TotpSetupResponse)
async def totp_setup(user: User = Depends(get_current_active_user)):
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, user.username)
    # Secret is returned but not persisted until the user verifies a code
    return TotpSetupResponse(secret=secret, uri=uri)


@router.post("/me/totp/verify", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def totp_verify(
    request: Request,
    body: TotpVerifyRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_totp(body.secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_TOTP_CODE", "message": "Invalid or expired TOTP code"})
    user.totp_secret = body.secret
    await db.commit()


@router.delete("/me/totp", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(
    body: TotpCodeRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if user.totp_secret is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "TOTP_NOT_ENABLED", "message": "TOTP is not enabled"})
    if not verify_totp(user.totp_secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_TOTP_CODE", "message": "Invalid or expired TOTP code"})
    user.totp_secret = None
    await db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "USER_NOT_FOUND", "message": "User not found"})
    user.is_active = False
    await db.commit()
