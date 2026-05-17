import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def test_register_returns_tokens_and_recovery_words(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={"username": "alice", "password": "securepass1"})
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["recovery_words"]) == 12


async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "bob", "password": "securepass1"})
    resp = await client.post("/api/auth/register", json={"username": "bob", "password": "securepass1"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_login(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "carol", "password": "securepass1"})
    resp = await client.post("/api/auth/token", data={"username": "carol", "password": "securepass1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "dave", "password": "securepass1"})
    resp = await client.post("/api/auth/token", data={"username": "dave", "password": "wrong"})
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/api/auth/register", json={"username": "eve", "password": "securepass1"})
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_token_rotation(client: AsyncClient):
    reg = await client.post("/api/auth/register", json={"username": "frank", "password": "securepass1"})
    refresh_token = reg.json()["refresh_token"]
    await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    # reusing the old refresh token should fail
    resp2 = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


async def test_account_recovery(client: AsyncClient):
    reg = await client.post("/api/auth/register", json={"username": "grace", "password": "securepass1"})
    words = reg.json()["recovery_words"]

    resp = await client.post("/api/auth/recover", json={
        "username": "grace",
        "recovery_words": words,
        "new_password": "newsecurepass1",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # old password no longer works
    bad = await client.post("/api/auth/token", data={"username": "grace", "password": "securepass1"})
    assert bad.status_code == 401

    # new password works
    good = await client.post("/api/auth/token", data={"username": "grace", "password": "newsecurepass1"})
    assert good.status_code == 200


async def test_recovery_wrong_words(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "heidi", "password": "securepass1"})
    resp = await client.post("/api/auth/recover", json={
        "username": "heidi",
        "recovery_words": ["wrong"] * 12,
        "new_password": "newpass123",
    })
    assert resp.status_code == 401


async def test_username_case_insensitive_register(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={"username": "CaseUser", "password": "securepass1"})
    assert resp.status_code == 201

    # Same username in different case should conflict
    resp2 = await client.post("/api/auth/register", json={"username": "caseuser", "password": "securepass1"})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_username_case_insensitive_login(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "MixedCase", "password": "securepass1"})

    # Login with uppercase should work
    resp = await client.post("/api/auth/token", data={"username": "MIXEDCASE", "password": "securepass1"})
    assert resp.status_code == 200

    # Login with lowercase should work
    resp2 = await client.post("/api/auth/token", data={"username": "mixedcase", "password": "securepass1"})
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# JSON login (/auth/login)
# ---------------------------------------------------------------------------

async def test_json_login(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "json_user", "password": "securepass1"})
    resp = await client.post("/api/auth/login", json={"username": "json_user", "password": "securepass1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_json_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "json_badpass", "password": "securepass1"})
    resp = await client.post("/api/auth/login", json={"username": "json_badpass", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


async def test_json_login_unknown_user(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={"username": "nobody", "password": "securepass1"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


async def test_json_login_case_insensitive(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "json_case", "password": "securepass1"})
    resp = await client.post("/api/auth/login", json={"username": "JSON_CASE", "password": "securepass1"})
    assert resp.status_code == 200


async def test_json_login_token_is_usable(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "json_usable", "password": "securepass1"})
    resp = await client.post("/api/auth/login", json={"username": "json_usable", "password": "securepass1"})
    token = resp.json()["access_token"]

    me = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "json_usable"


async def test_json_login_refresh_token_is_rotatable(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "json_refresh", "password": "securepass1"})
    resp = await client.post("/api/auth/login", json={"username": "json_refresh", "password": "securepass1"})
    refresh_token = resp.json()["refresh_token"]

    rotated = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    assert "access_token" in rotated.json()
