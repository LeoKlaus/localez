"""Integration tests for the passkey (WebAuthn) registration and authentication flow."""
import pytest
from httpx import AsyncClient

from app.core.security import decode_webauthn_challenge_token
from tests.soft_authenticator import SoftAuthenticator

pytestmark = pytest.mark.usefixtures("setup_database")

RP_ID = "localhost"
ORIGIN = "http://localhost:8000"


def _make_authenticator() -> SoftAuthenticator:
    return SoftAuthenticator(RP_ID, ORIGIN)


def _challenge_from_token(challenge_token: str) -> bytes:
    return decode_webauthn_challenge_token(challenge_token)


# ---------------------------------------------------------------------------
# Registration begin
# ---------------------------------------------------------------------------

async def test_passkey_register_begin_requires_auth(client: AsyncClient):
    resp = await client.post("/api/auth/passkey/register/begin")
    assert resp.status_code == 401


async def test_passkey_register_begin_returns_options(client: AsyncClient, unique_username):
    username = unique_username("pk_begin")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]

    resp = await client.post(
        "/api/auth/passkey/register/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "options" in data
    assert "challenge_token" in data
    assert "challenge" in data["options"]
    assert data["options"]["rp"]["id"] == RP_ID


# ---------------------------------------------------------------------------
# Registration complete
# ---------------------------------------------------------------------------

async def test_passkey_register_complete_success(client: AsyncClient, unique_username):
    username = unique_username("pk_reg")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    begin = (await client.post("/api/auth/passkey/register/begin", headers=headers)).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    auth = _make_authenticator()
    resp = await client.post(
        "/api/auth/passkey/register/complete",
        headers=headers,
        json={
            "credential": auth.registration_response(challenge),
            "challenge_token": begin["challenge_token"],
            "name": "Test Key",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["message"] == "Passkey registered"


async def test_passkey_register_complete_wrong_challenge(client: AsyncClient, unique_username):
    username = unique_username("pk_badchallenge")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    begin = (await client.post("/api/auth/passkey/register/begin", headers=headers)).json()

    # Produce a credential for a *different* challenge
    import os
    wrong_challenge = os.urandom(32)
    auth = _make_authenticator()
    resp = await client.post(
        "/api/auth/passkey/register/complete",
        headers=headers,
        json={
            "credential": auth.registration_response(wrong_challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PASSKEY_REGISTRATION_FAILED"


async def test_passkey_register_complete_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/auth/passkey/register/complete",
        json={"credential": {}, "challenge_token": "fake"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authentication begin
# ---------------------------------------------------------------------------

async def test_passkey_auth_begin_returns_options(client: AsyncClient):
    resp = await client.post("/api/auth/passkey/authenticate/begin")
    assert resp.status_code == 200
    data = resp.json()
    assert "options" in data
    assert "challenge_token" in data
    assert "challenge" in data["options"]


# ---------------------------------------------------------------------------
# Authentication complete — full round-trip
# ---------------------------------------------------------------------------

async def _register_passkey(client: AsyncClient, username: str, password: str = "securepass1"):
    """Helper: register a user, add a passkey, return (access_token, authenticator)."""
    reg = await client.post("/api/auth/register", json={"username": username, "password": password})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    begin = (await client.post("/api/auth/passkey/register/begin", headers=headers)).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    auth = _make_authenticator()
    complete = await client.post(
        "/api/auth/passkey/register/complete",
        headers=headers,
        json={
            "credential": auth.registration_response(challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert complete.status_code == 201
    return token, auth


async def test_passkey_auth_complete_success(client: AsyncClient, unique_username):
    username = unique_username("pk_authn")
    _, auth = await _register_passkey(client, username)

    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    resp = await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={
            "credential": auth.authentication_response(challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_passkey_auth_complete_wrong_challenge(client: AsyncClient, unique_username):
    username = unique_username("pk_authn_bad")
    _, auth = await _register_passkey(client, username)

    import os
    wrong_challenge = os.urandom(32)
    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()

    resp = await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={
            "credential": auth.authentication_response(wrong_challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "PASSKEY_AUTH_FAILED"


async def test_passkey_auth_unknown_credential(client: AsyncClient):
    """A credential ID the server has never seen returns 401."""
    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    auth = _make_authenticator()
    resp = await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={
            "credential": auth.authentication_response(challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "PASSKEY_AUTH_FAILED"


async def test_passkey_tokens_are_usable(client: AsyncClient, unique_username):
    """Tokens issued via passkey auth can access protected endpoints."""
    username = unique_username("pk_tokens")
    _, auth = await _register_passkey(client, username)

    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    tokens = (await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={
            "credential": auth.authentication_response(challenge),
            "challenge_token": begin["challenge_token"],
        },
    )).json()

    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == username
