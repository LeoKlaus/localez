import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def test_admin_can_create_project(admin_client: AsyncClient):
    resp = await admin_client.post("/api/projects", json={"name": "My App", "source_language": "en"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "My App"


async def test_user_cannot_create_project(client: AsyncClient):
    await client.post("/api/auth/register", json={"username": "plain_user", "password": "securepass1"})
    resp2 = await client.post("/api/auth/token", data={"username": "plain_user", "password": "securepass1"})
    token = resp2.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    resp = await client.post("/api/projects", json={"name": "Should Fail", "source_language": "en"})
    assert resp.status_code == 403


async def test_admin_can_grant_language_role(admin_client: AsyncClient):
    await admin_client.post("/api/auth/register", json={"username": "lang_role_member", "password": "securepass1"})
    proj = (await admin_client.post("/api/projects", json={"name": "Membership Test", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})

    users = (await admin_client.get("/api/users?limit=200")).json()
    member_user = next(u for u in users if u["username"] == "lang_role_member")

    resp = await admin_client.put(
        f"/api/projects/{proj['id']}/members/{member_user['id']}/language-roles/de",
        json={"role": "translator"},
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == member_user["id"]
    assert resp.json()["language"] == "de"
    assert resp.json()["role"] == "translator"
