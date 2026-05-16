import secrets
import uuid
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, hash_token
from app.database import get_db
from app.models.project_token import ProjectToken
from app.models.user import GlobalRole, User

TOKEN_PREFIX = "lz_"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def generate_project_token() -> tuple[str, str]:
    """Return (raw_token, token_hash). Raw token is shown once and never stored."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


async def require_import_access(
    project_id: uuid.UUID,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    if token.startswith(TOKEN_PREFIX):
        pt = await db.scalar(
            select(ProjectToken).where(ProjectToken.token_hash == hash_token(token))
        )
        if pt is None or pt.project_id != project_id:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "Invalid or revoked project token"},
            )
        pt.last_used_at = datetime.now(UTC)
        return

    # JWT path — must be an active admin
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
