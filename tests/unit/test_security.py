"""Unit tests for app.core.security — no DB required."""
import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_webauthn_challenge_token,
    decode_access_token,
    decode_webauthn_challenge_token,
    hash_password,
    hash_token,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_password_is_not_plaintext():
    h = hash_password("mysecret")
    assert h != "mysecret"


def test_hash_password_starts_with_bcrypt_prefix():
    h = hash_password("mysecret")
    assert h.startswith("$2b$")


def test_verify_password_correct():
    h = hash_password("correct-horse")
    assert verify_password("correct-horse", h) is True


def test_verify_password_wrong():
    h = hash_password("correct-horse")
    assert verify_password("wrong-horse", h) is False


def test_hash_password_different_salts():
    h1 = hash_password("same")
    h2 = hash_password("same")
    # bcrypt produces different hashes each time due to random salt
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------

def test_hash_token_is_hex():
    result = hash_token("some-raw-token")
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_token_is_64_chars():
    # SHA-256 → 32 bytes → 64 hex chars
    assert len(hash_token("anything")) == 64


def test_hash_token_deterministic():
    assert hash_token("abc") == hash_token("abc")


def test_hash_token_different_inputs():
    assert hash_token("a") != hash_token("b")


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------

def test_access_token_round_trip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "user")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_access_token_admin_role():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "admin")
    payload = decode_access_token(token)
    assert payload["role"] == "admin"


def test_decode_access_token_rejects_garbage():
    with pytest.raises(ValueError):
        decode_access_token("not.a.token")


def test_decode_access_token_rejects_wrong_type():
    # Build a webauthn challenge token and try to decode it as access token
    challenge_token = create_webauthn_challenge_token(b"\x01\x02\x03")
    with pytest.raises(ValueError, match="Not an access token"):
        decode_access_token(challenge_token)


# ---------------------------------------------------------------------------
# WebAuthn challenge token
# ---------------------------------------------------------------------------

def test_webauthn_challenge_token_round_trip():
    challenge = b"\xde\xad\xbe\xef" * 8
    token = create_webauthn_challenge_token(challenge)
    recovered = decode_webauthn_challenge_token(token)
    assert recovered == challenge


def test_webauthn_challenge_token_rejects_garbage():
    with pytest.raises(ValueError):
        decode_webauthn_challenge_token("not.a.token")


def test_webauthn_challenge_token_rejects_wrong_type():
    user_id = uuid.uuid4()
    access_token = create_access_token(user_id, "user")
    with pytest.raises(ValueError, match="Not a webauthn challenge token"):
        decode_webauthn_challenge_token(access_token)
