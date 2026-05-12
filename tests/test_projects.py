import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def test_admin_can_create_project(admin_client: AsyncClient):
    resp = await admin_client.post("/projects", json={"name": "My App", "source_language": "en"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "My App"


async def test_user_cannot_create_project(client: AsyncClient):
    await client.post("/auth/register", json={"username": "plain_user", "password": "securepass1"})
    resp2 = await client.post("/auth/token", data={"username": "plain_user", "password": "securepass1"})
    token = resp2.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    resp = await client.post("/projects", json={"name": "Should Fail", "source_language": "en"})
    assert resp.status_code == 403


async def test_admin_can_add_member(admin_client: AsyncClient):
    # create a regular user first
    reg = await admin_client.post("/auth/register", json={"username": "new_member", "password": "securepass1"})
    # admin_client is already authed as admin
    proj = await admin_client.post("/projects", json={"name": "Membership Test", "source_language": "en"})
    project_id = proj.json()["id"]

    # get user id
    users_resp = await admin_client.get("/users")
    users = users_resp.json()
    member_user = next(u for u in users if u["username"] == "new_member")

    resp = await admin_client.post(f"/projects/{project_id}/members", json={
        "user_id": member_user["id"],
        "project_role": "translator",
    })
    assert resp.status_code == 201
    assert resp.json()["project_role"] == "translator"
