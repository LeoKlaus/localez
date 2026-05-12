import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.recovery import generate_recovery_words, hash_recovery_words, verify_recovery_words
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import GlobalRole, User


async def register_user(db: AsyncSession, username: str, password: str) -> tuple[User, list[str], str, str]:
    recovery_words = generate_recovery_words()
    user = User(
        username=username,
        hashed_password=hash_password(password),
        global_role=GlobalRole.user,
        recovery_word_hash=hash_recovery_words(recovery_words),
    )
    db.add(user)
    await db.flush()

    access_token, refresh_token_raw = await _issue_tokens(db, user)
    return user, recovery_words, access_token, refresh_token_raw


async def authenticate_user(db: AsyncSession, username: str, password: str) -> tuple[User, str, str] | None:
    result = await db.execute(select(User).where(User.username == username, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    access_token, refresh_token_raw = await _issue_tokens(db, user)
    return user, access_token, refresh_token_raw


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[str, str] | None:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        return None

    stored.revoked = True
    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        return None

    access_token, new_refresh_raw = await _issue_tokens(db, user)
    return access_token, new_refresh_raw


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True


async def recover_account(db: AsyncSession, username: str, words: list[str], new_password: str) -> tuple[str, str] | None:
    result = await db.execute(select(User).where(User.username == username, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if user is None or not verify_recovery_words(words, user.recovery_word_hash):
        return None

    user.hashed_password = hash_password(new_password)

    # revoke all existing refresh tokens
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
    )

    access_token, refresh_token_raw = await _issue_tokens(db, user)
    return access_token, refresh_token_raw


async def _issue_tokens(db: AsyncSession, user: User) -> tuple[str, str]:
    raw, token_hash, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    access_token = create_access_token(user.id, user.global_role.value)
    return access_token, raw
