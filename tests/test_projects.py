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


