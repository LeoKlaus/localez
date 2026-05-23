"""Tests for cookie-based auth endpoints and the basic token logout endpoint."""
import pytest
from httpx import AsyncClient

from tests.test_passkey import _make_authenticator, _challenge_from_token, _register_passkey

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# POST /auth/logout  (bearer-based)
# ---------------------------------------------------------------------------

async def test_logout_revokes_refresh_token(client: AsyncClient, unique_username):
    username = unique_username("logout_user")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    refresh_token = reg.json()["refresh_token"]

    resp = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 204

    # The refresh token should no longer work
    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register/cookie
# ---------------------------------------------------------------------------

async def test_register_cookie_creates_account_and_sets_cookie(client: AsyncClient, unique_username):
    username = unique_username("cookie_reg")
    resp = await client.post(
        "/api/auth/register/cookie",
        json={"username": username, "password": "securepass1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "recovery_words" in data
    assert len(data["recovery_words"]) == 12
    # Cookie should be set
    assert "lz_refresh" in resp.cookies


async def test_register_cookie_duplicate_username_returns_409(client: AsyncClient, unique_username):
    username = unique_username("cookie_dup")
    await client.post(
        "/api/auth/register/cookie",
        json={"username": username, "password": "securepass1"},
    )
    resp = await client.post(
        "/api/auth/register/cookie",
        json={"username": username, "password": "securepass1"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


# ---------------------------------------------------------------------------
# POST /auth/login/cookie
# ---------------------------------------------------------------------------

async def test_login_cookie_returns_access_token_and_sets_cookie(client: AsyncClient, unique_username):
    username = unique_username("cookie_login")
    await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})

    resp = await client.post(
        "/api/auth/login/cookie",
        json={"username": username, "password": "securepass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "lz_refresh" in resp.cookies


async def test_login_cookie_wrong_password_returns_401(client: AsyncClient, unique_username):
    username = unique_username("cookie_badlogin")
    await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})

    resp = await client.post(
        "/api/auth/login/cookie",
        json={"username": username, "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# POST /auth/refresh/cookie
# ---------------------------------------------------------------------------

async def test_refresh_cookie_rotates_token(client: AsyncClient, unique_username):
    username = unique_username("cookie_refresh")
    login = (await client.post(
        "/api/auth/login/cookie",
        json={"username": username, "password": "securepass1"},
    ) if False else await _do_register_and_login_cookie(client, username))

    resp = await client.post("/api/auth/refresh/cookie")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    # A new cookie should be issued
    assert "lz_refresh" in resp.cookies


async def test_refresh_cookie_missing_cookie_returns_401(client: AsyncClient):
    # Make sure no cookie is present
    client.cookies.clear()
    resp = await client.post("/api/auth/refresh/cookie")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "MISSING_REFRESH_TOKEN"


async def test_refresh_cookie_invalid_token_returns_401(client: AsyncClient, unique_username):
    username = unique_username("cookie_invalid_refresh")
    await _do_register_and_login_cookie(client, username)
    # Log out first so the refresh token is revoked
    await client.post("/api/auth/logout/cookie")
    # Now try to refresh with the revoked cookie (still present from the logout response clearing the cookie
    # isn't guaranteed in the test client — force an invalid value)
    client.cookies.set("lz_refresh", "revoked-or-invalid-token")
    resp = await client.post("/api/auth/refresh/cookie")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


# ---------------------------------------------------------------------------
# POST /auth/logout/cookie
# ---------------------------------------------------------------------------

async def test_logout_cookie_clears_cookie(client: AsyncClient, unique_username):
    username = unique_username("cookie_logout")
    await _do_register_and_login_cookie(client, username)

    resp = await client.post("/api/auth/logout/cookie")
    assert resp.status_code == 204
    # The cookie should be cleared (empty or absent)
    assert client.cookies.get("lz_refresh") in (None, "")


async def test_logout_cookie_without_cookie_still_returns_204(client: AsyncClient):
    client.cookies.clear()
    resp = await client.post("/api/auth/logout/cookie")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# POST /auth/passkey/authenticate/complete/cookie
# ---------------------------------------------------------------------------

async def test_passkey_auth_complete_cookie_success(client: AsyncClient, unique_username):
    username = unique_username("pk_cookie_authn")
    _, auth = await _register_passkey(client, username)

    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    challenge = _challenge_from_token(begin["challenge_token"])

    resp = await client.post(
        "/api/auth/passkey/authenticate/complete/cookie",
        json={
            "credential": auth.authentication_response(challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "lz_refresh" in resp.cookies


async def test_passkey_auth_complete_cookie_wrong_challenge(client: AsyncClient, unique_username):
    import os
    username = unique_username("pk_cookie_bad")
    _, auth = await _register_passkey(client, username)

    begin = (await client.post("/api/auth/passkey/authenticate/begin")).json()
    wrong_challenge = os.urandom(32)

    resp = await client.post(
        "/api/auth/passkey/authenticate/complete/cookie",
        json={
            "credential": auth.authentication_response(wrong_challenge),
            "challenge_token": begin["challenge_token"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "PASSKEY_AUTH_FAILED"


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

async def _do_register_and_login_cookie(client: AsyncClient, username: str) -> None:
    """Register a user and log in via the cookie endpoint, setting lz_refresh on the client."""
    await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    await client.post(
        "/api/auth/login/cookie",
        json={"username": username, "password": "securepass1"},
    )
