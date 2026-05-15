"""Integration tests for /users endpoints."""
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def test_get_me(client: AsyncClient, unique_username):
    username = unique_username("me")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == username
    assert data["global_role"] == "user"
    assert data["is_active"] is True


async def test_get_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_update_password(client: AsyncClient, unique_username):
    username = unique_username("pw")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "oldpass123"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.patch("/api/users/me", json={"current_password": "oldpass123", "new_password": "newpass123"})
    assert resp.status_code == 200

    bad = await client.post("/api/auth/token", data={"username": username, "password": "oldpass123"})
    assert bad.status_code == 401

    good = await client.post("/api/auth/token", data={"username": username, "password": "newpass123"})
    assert good.status_code == 200


async def test_update_password_wrong_current(client: AsyncClient, unique_username):
    username = unique_username("pwwrong")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "pass12345"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.patch("/api/users/me", json={"current_password": "wrongpass", "new_password": "newpass123"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "WRONG_PASSWORD"


async def test_update_password_too_short(client: AsyncClient, unique_username):
    username = unique_username("pwshort")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "pass12345"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.patch("/api/users/me", json={"current_password": "pass12345", "new_password": "short"})
    assert resp.status_code == 422


async def test_list_users_requires_admin(client: AsyncClient, unique_username):
    username = unique_username("list")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.get("/api/users")
    assert resp.status_code == 403


async def test_admin_can_list_users(admin_client: AsyncClient, client: AsyncClient, unique_username):
    # Create a regular user so there's something to list
    username = unique_username("listed")
    await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})

    resp = await admin_client.get("/api/users?limit=200")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert "X-Total-Count" in resp.headers
    usernames = [u["username"] for u in resp.json()]
    assert username in usernames


async def test_admin_list_users_pagination(admin_client: AsyncClient):
    resp = await admin_client.get("/api/users?limit=1&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1
    assert "X-Total-Count" in resp.headers


async def test_admin_can_get_user_by_id(admin_client: AsyncClient, client: AsyncClient, unique_username):
    username = unique_username("byid")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    user_id = (await client.get("/api/users/me")).json()["id"]

    resp = await admin_client.get(f"/api/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["username"] == username


async def test_admin_get_nonexistent_user(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/users/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_admin_can_promote_user_to_admin(admin_client: AsyncClient, client: AsyncClient, unique_username):
    username = unique_username("promote")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    user_id = (await client.get("/api/users/me")).json()["id"]

    resp = await admin_client.patch(f"/api/users/{user_id}/role", json={"global_role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["global_role"] == "admin"


async def test_admin_can_demote_admin(admin_client: AsyncClient, client: AsyncClient, unique_username):
    username = unique_username("demote")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    user_id = (await client.get("/api/users/me")).json()["id"]

    await admin_client.patch(f"/api/users/{user_id}/role", json={"global_role": "admin"})
    resp = await admin_client.patch(f"/api/users/{user_id}/role", json={"global_role": "user"})
    assert resp.status_code == 200
    assert resp.json()["global_role"] == "user"


async def test_admin_can_deactivate_user(admin_client: AsyncClient, client: AsyncClient, unique_username):
    username = unique_username("deactivate")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    user_id = (await client.get("/api/users/me")).json()["id"]

    resp = await admin_client.delete(f"/api/users/{user_id}")
    assert resp.status_code == 204

    # deactivated user cannot log in
    login = await client.post("/api/auth/token", data={"username": username, "password": "securepass1"})
    assert login.status_code == 401


async def test_non_admin_cannot_update_role(client: AsyncClient, unique_username):
    username = unique_username("norole")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.patch(f"/api/users/{uuid.uuid4()}/role", json={"global_role": "admin"})
    assert resp.status_code == 403


async def test_non_admin_cannot_delete_user(client: AsyncClient, unique_username):
    username = unique_username("nodelete")
    reg = await client.post("/api/auth/register", json={"username": username, "password": "securepass1"})
    client.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"

    resp = await client.delete(f"/api/users/{uuid.uuid4()}")
    assert resp.status_code == 403
