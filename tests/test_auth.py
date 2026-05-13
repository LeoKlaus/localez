import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def test_register_returns_tokens_and_recovery_words(client: AsyncClient):
    resp = await client.post("/auth/register", json={"username": "alice", "password": "securepass1"})
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["recovery_words"]) == 12


async def test_register_duplicate_username(client: AsyncClient):
    await client.post("/auth/register", json={"username": "bob", "password": "securepass1"})
    resp = await client.post("/auth/register", json={"username": "bob", "password": "securepass1"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_login(client: AsyncClient):
    await client.post("/auth/register", json={"username": "carol", "password": "securepass1"})
    resp = await client.post("/auth/token", data={"username": "carol", "password": "securepass1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={"username": "dave", "password": "securepass1"})
    resp = await client.post("/auth/token", data={"username": "dave", "password": "wrong"})
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient):
    reg = await client.post("/auth/register", json={"username": "eve", "password": "securepass1"})
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_refresh_token_rotation(client: AsyncClient):
    reg = await client.post("/auth/register", json={"username": "frank", "password": "securepass1"})
    refresh_token = reg.json()["refresh_token"]
    await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    # reusing the old refresh token should fail
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


async def test_account_recovery(client: AsyncClient):
    reg = await client.post("/auth/register", json={"username": "grace", "password": "securepass1"})
    words = reg.json()["recovery_words"]

    resp = await client.post("/auth/recover", json={
        "username": "grace",
        "recovery_words": words,
        "new_password": "newsecurepass1",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # old password no longer works
    bad = await client.post("/auth/token", data={"username": "grace", "password": "securepass1"})
    assert bad.status_code == 401

    # new password works
    good = await client.post("/auth/token", data={"username": "grace", "password": "newsecurepass1"})
    assert good.status_code == 200


async def test_recovery_wrong_words(client: AsyncClient):
    await client.post("/auth/register", json={"username": "heidi", "password": "securepass1"})
    resp = await client.post("/auth/recover", json={
        "username": "heidi",
        "recovery_words": ["wrong"] * 12,
        "new_password": "newpass123",
    })
    assert resp.status_code == 401


async def test_username_case_insensitive_register(client: AsyncClient):
    resp = await client.post("/auth/register", json={"username": "CaseUser", "password": "securepass1"})
    assert resp.status_code == 201

    # Same username in different case should conflict
    resp2 = await client.post("/auth/register", json={"username": "caseuser", "password": "securepass1"})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_username_case_insensitive_login(client: AsyncClient):
    await client.post("/auth/register", json={"username": "MixedCase", "password": "securepass1"})

    # Login with uppercase should work
    resp = await client.post("/auth/token", data={"username": "MIXEDCASE", "password": "securepass1"})
    assert resp.status_code == 200

    # Login with lowercase should work
    resp2 = await client.post("/auth/token", data={"username": "mixedcase", "password": "securepass1"})
    assert resp2.status_code == 200
