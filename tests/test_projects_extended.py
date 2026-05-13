"""Additional integration tests for /projects and /projects/{id}/members."""
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

async def test_list_projects_admin_sees_all(admin_client: AsyncClient):
    await admin_client.post("/projects", json={"name": "ListAll A", "source_language": "en"})
    await admin_client.post("/projects", json={"name": "ListAll B", "source_language": "fr"})

    resp = await admin_client.get("/projects")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    names = [p["name"] for p in resp.json()]
    assert "ListAll A" in names
    assert "ListAll B" in names


async def test_list_projects_member_sees_only_own(
    admin_client: AsyncClient, member_client, unique_username
):
    username = unique_username("listmember")
    proj_visible = (await admin_client.post("/projects", json={"name": "Visible Project", "source_language": "en"})).json()
    await admin_client.post("/projects", json={"name": "Hidden Project", "source_language": "en"})

    async with member_client(username) as c:
        users = (await admin_client.get("/users")).json()
        user = next(u for u in users if u["username"] == username)
        await admin_client.post(f"/projects/{proj_visible['id']}/members", json={
            "user_id": user["id"], "project_role": "guest",
        })

        resp = await c.get("/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Visible Project" in names
        assert "Hidden Project" not in names


async def test_list_projects_unauthenticated(client: AsyncClient):
    resp = await client.get("/projects")
    assert resp.status_code == 401


async def test_get_project_as_admin(admin_client: AsyncClient, project: dict):
    resp = await admin_client.get(f"/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


async def test_get_project_as_member(admin_client: AsyncClient, member_client, unique_username, project: dict):
    username = unique_username("getmember")
    async with member_client(username) as c:
        users = (await admin_client.get("/users")).json()
        user = next(u for u in users if u["username"] == username)
        await admin_client.post(f"/projects/{project['id']}/members", json={
            "user_id": user["id"], "project_role": "guest",
        })

        resp = await c.get(f"/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project["id"]


async def test_get_project_non_member_gets_403(member_client, unique_username, project: dict):
    username = unique_username("nonmember")
    async with member_client(username) as c:
        resp = await c.get(f"/projects/{project['id']}")
        assert resp.status_code == 403


async def test_get_project_not_found(admin_client: AsyncClient):
    resp = await admin_client.get(f"/projects/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_update_project(admin_client: AsyncClient, project: dict):
    resp = await admin_client.patch(f"/projects/{project['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_update_project_source_language(admin_client: AsyncClient, project: dict):
    resp = await admin_client.patch(f"/projects/{project['id']}", json={"source_language": "fr"})
    assert resp.status_code == 200
    assert resp.json()["source_language"] == "fr"


async def test_update_project_non_admin_gets_403(member_client, unique_username, project: dict):
    username = unique_username("noupdate")
    async with member_client(username) as c:
        resp = await c.patch(f"/projects/{project['id']}", json={"name": "Should fail"})
        assert resp.status_code == 403


async def test_delete_project(admin_client: AsyncClient):
    proj = (await admin_client.post("/projects", json={"name": "To Delete", "source_language": "en"})).json()
    resp = await admin_client.delete(f"/projects/{proj['id']}")
    assert resp.status_code == 204

    get_resp = await admin_client.get(f"/projects/{proj['id']}")
    assert get_resp.status_code == 404


async def test_delete_project_non_admin_gets_403(member_client, unique_username, project: dict):
    username = unique_username("nodelete")
    async with member_client(username) as c:
        resp = await c.delete(f"/projects/{project['id']}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

async def test_list_members(admin_client: AsyncClient, project: dict, client: AsyncClient, unique_username):
    username = unique_username("listed_member")
    await client.post("/auth/register", json={"username": username, "password": "securepass1"})
    users = (await admin_client.get("/users")).json()
    user = next(u for u in users if u["username"] == username)
    await admin_client.post(f"/projects/{project['id']}/members", json={
        "user_id": user["id"], "project_role": "translator",
    })

    resp = await admin_client.get(f"/projects/{project['id']}/members")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    member_ids = [m["user_id"] for m in resp.json()]
    assert str(user["id"]) in member_ids


async def test_add_member_duplicate_returns_409(
    admin_client: AsyncClient, project: dict, client: AsyncClient, unique_username
):
    username = unique_username("dup_member")
    await client.post("/auth/register", json={"username": username, "password": "securepass1"})
    users = (await admin_client.get("/users")).json()
    user = next(u for u in users if u["username"] == username)

    payload = {"user_id": user["id"], "project_role": "guest"}
    await admin_client.post(f"/projects/{project['id']}/members", json=payload)
    resp = await admin_client.post(f"/projects/{project['id']}/members", json=payload)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_MEMBER"


async def test_update_member_role(admin_client: AsyncClient, project: dict, client: AsyncClient, unique_username):
    username = unique_username("updaterole")
    await client.post("/auth/register", json={"username": username, "password": "securepass1"})
    users = (await admin_client.get("/users")).json()
    user = next(u for u in users if u["username"] == username)
    await admin_client.post(f"/projects/{project['id']}/members", json={
        "user_id": user["id"], "project_role": "guest",
    })

    resp = await admin_client.patch(
        f"/projects/{project['id']}/members/{user['id']}",
        json={"project_role": "reviewer"},
    )
    assert resp.status_code == 200
    assert resp.json()["project_role"] == "reviewer"


async def test_remove_member(admin_client: AsyncClient, project: dict, client: AsyncClient, unique_username):
    username = unique_username("removemember")
    await client.post("/auth/register", json={"username": username, "password": "securepass1"})
    users = (await admin_client.get("/users")).json()
    user = next(u for u in users if u["username"] == username)
    await admin_client.post(f"/projects/{project['id']}/members", json={
        "user_id": user["id"], "project_role": "guest",
    })

    resp = await admin_client.delete(f"/projects/{project['id']}/members/{user['id']}")
    assert resp.status_code == 204

    # user can no longer access the project
    token = (await client.post("/auth/token", data={"username": username, "password": "securepass1"})).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    get_resp = await client.get(f"/projects/{project['id']}")
    assert get_resp.status_code == 403


async def test_remove_nonexistent_member_returns_404(admin_client: AsyncClient, project: dict):
    resp = await admin_client.delete(f"/projects/{project['id']}/members/{uuid.uuid4()}")
    assert resp.status_code == 404
