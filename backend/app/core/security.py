import hashlib
import secrets
import uuid
import bcrypt
from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings


ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8"),
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID, global_role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "role": global_role, "exp": expire, "type": "access"},
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    token_hash = hash_token(raw)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return raw, token_hash, expires_at


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        return payload
    except InvalidTokenError as e:
        raise ValueError("Invalid token") from e


def create_webauthn_challenge_token(challenge: bytes) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=5)
    return jwt.encode(
        {"challenge": challenge.hex(), "exp": expire, "type": "webauthn_challenge"},
        settings.secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_webauthn_challenge_token(token: str) -> bytes:
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[ALGORITHM])
        if payload.get("type") != "webauthn_challenge":
            raise ValueError("Not a webauthn challenge token")
        return bytes.fromhex(payload["challenge"])
    except InvalidTokenError as e:
        raise ValueError("Invalid challenge token") from e
