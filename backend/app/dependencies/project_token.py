import secrets
import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, hash_token
from app.database import get_db
from app.models.project_token import ProjectToken, TokenType
from app.models.user import GlobalRole, User

IMPORT_TOKEN_PREFIX = "lz_"
EXPORT_TOKEN_PREFIX = "lzr_"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def generate_project_token(token_type: TokenType = TokenType.import_) -> tuple[str, str]:
    """Return (raw_token, token_hash). Raw token is shown once and never stored."""
    prefix = EXPORT_TOKEN_PREFIX if token_type == TokenType.export else IMPORT_TOKEN_PREFIX
    raw = prefix + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


async def _resolve_project_token(
    token: str,
    project_id: uuid.UUID,
    expected_type: TokenType,
    db: AsyncSession,
) -> bool:
    """Look up a project token by hash, validate project and type.

    Returns True if the token is valid, raises HTTPException otherwise.
    """
    pt = await db.scalar(
        select(ProjectToken).where(ProjectToken.token_hash == hash_token(token))
    )
    if pt is None or pt.project_id != project_id or pt.token_type != expected_type:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or revoked project token"},
        )
    pt.last_used_at = datetime.now(UTC)
    return True


async def _require_jwt_admin(token: str, db: AsyncSession) -> None:
    """Validate a JWT bearer token and assert global admin role."""
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )
    if user.global_role != GlobalRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "Insufficient global role"},
        )


async def require_import_access(
    project_id: uuid.UUID,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    if token.startswith(IMPORT_TOKEN_PREFIX):
        await _resolve_project_token(token, project_id, TokenType.import_, db)
        return
    await _require_jwt_admin(token, db)


async def require_export_access(
    project_id: uuid.UUID,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    if token.startswith(EXPORT_TOKEN_PREFIX):
        await _resolve_project_token(token, project_id, TokenType.export, db)
        return
    await _require_jwt_admin(token, db)
