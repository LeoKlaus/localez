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


# ---------------------------------------------------------------------------
# Credential management — list
# ---------------------------------------------------------------------------

async def test_list_credentials_requires_auth(client: AsyncClient):
    resp = await client.get("/api/auth/passkey/credentials")
    assert resp.status_code == 401


async def test_list_credentials_empty(client: AsyncClient, unique_username):
    username = unique_username("pk_list_empty")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]

    resp = await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_credentials_returns_registered_passkey(client: AsyncClient, unique_username):
    username = unique_username("pk_list")
    token, _ = await _register_passkey(client, username)

    resp = await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "id" in data[0]
    assert "name" in data[0]
    assert "aaguid" in data[0]


async def test_list_credentials_only_returns_own(client: AsyncClient, unique_username):
    username_a = unique_username("pk_list_a")
    username_b = unique_username("pk_list_b")
    token_a, _ = await _register_passkey(client, username_a)
    token_b, _ = await _register_passkey(client, username_b)

    resp = await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token_a}"})
    cred_ids = {c["id"] for c in resp.json()}

    resp_b = await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token_b}"})
    other_ids = {c["id"] for c in resp_b.json()}

    assert cred_ids.isdisjoint(other_ids)


async def test_list_credentials_multiple(client: AsyncClient, unique_username):
    username = unique_username("pk_list_multi")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for name in ("Key A", "Key B"):
        begin = (await client.post("/api/auth/passkey/register/begin", headers=headers)).json()
        challenge = _challenge_from_token(begin["challenge_token"])
        auth = _make_authenticator()
        await client.post(
            "/api/auth/passkey/register/complete",
            headers=headers,
            json={"credential": auth.registration_response(challenge), "challenge_token": begin["challenge_token"], "name": name},
        )

    resp = await client.get("/api/auth/passkey/credentials", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert {c["name"] for c in resp.json()} == {"Key A", "Key B"}


# ---------------------------------------------------------------------------
# Credential management — delete
# ---------------------------------------------------------------------------

async def test_delete_credential_requires_auth(client: AsyncClient, unique_username):
    username = unique_username("pk_del_noauth")
    token, _ = await _register_passkey(client, username)
    cred_id = (await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token}"})).json()[0]["id"]

    resp = await client.delete(f"/api/auth/passkey/credentials/{cred_id}")
    assert resp.status_code == 401


async def test_delete_credential_success(client: AsyncClient, unique_username):
    username = unique_username("pk_del")
    token, _ = await _register_passkey(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    cred_id = (await client.get("/api/auth/passkey/credentials", headers=headers)).json()[0]["id"]

    resp = await client.delete(f"/api/auth/passkey/credentials/{cred_id}", headers=headers)
    assert resp.status_code == 204

    remaining = (await client.get("/api/auth/passkey/credentials", headers=headers)).json()
    assert not any(c["id"] == cred_id for c in remaining)


async def test_delete_credential_not_found(client: AsyncClient, unique_username):
    import uuid
    username = unique_username("pk_del_404")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    token = reg.json()["access_token"]

    resp = await client.delete(f"/api/auth/passkey/credentials/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CREDENTIAL_NOT_FOUND"


async def test_delete_credential_cannot_delete_other_users(client: AsyncClient, unique_username):
    username_a = unique_username("pk_del_cross_a")
    username_b = unique_username("pk_del_cross_b")
    token_a, _ = await _register_passkey(client, username_a)
    reg_b = await client.post("/api/auth/register", json={"username": username_b, "password": "securepass1"})
    token_b = reg_b.json()["access_token"]

    cred_id = (await client.get("/api/auth/passkey/credentials", headers={"Authorization": f"Bearer {token_a}"})).json()[0]["id"]

    resp = await client.delete(f"/api/auth/passkey/credentials/{cred_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


async def test_deleted_credential_cannot_authenticate(client: AsyncClient, unique_username):
    username = unique_username("pk_del_auth")
    token, auth = await _register_passkey(client, username)
    headers = {"Authorization": f"Bearer {token}"}
    cred_id = (await client.get("/api/auth/passkey/credentials", headers=headers)).json()[0]["id"]

    await client.delete(f"/api/auth/passkey/credentials/{cred_id}", headers=headers)

    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    challenge = _challenge_from_token(begin["challenge_token"])
    resp = await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={"credential": auth.authentication_response(challenge), "challenge_token": begin["challenge_token"]},
    )
    assert resp.status_code == 401


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
