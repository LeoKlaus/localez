"""Tests for project description field."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_project(client: AsyncClient, name: str, description: str | None = None) -> dict:
    body: dict = {"name": name, "source_language": "en"}
    if description is not None:
        body["description"] = description
    resp = await client.post("/api/projects", json=body)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_project_with_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescCreate", description="Hello **world**")
    assert proj["description"] == "Hello **world**"


async def test_create_project_without_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescNone")
    assert proj["description"] is None


async def test_create_project_description_null_explicit(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/projects",
        json={"name": "DescNullExplicit", "source_language": "en", "description": None},
    )
    assert resp.status_code == 201
    assert resp.json()["description"] is None


async def test_create_project_description_max_length(admin_client: AsyncClient):
    long_desc = "x" * 10_000
    proj = await _create_project(admin_client, "DescMaxLen", description=long_desc)
    assert proj["description"] == long_desc


async def test_create_project_description_too_long(admin_client: AsyncClient):
    too_long = "x" * 10_001
    resp = await admin_client.post(
        "/api/projects",
        json={"name": "DescTooLong", "source_language": "en", "description": too_long},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def test_get_project_returns_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescGet", description="## Title\nBody text.")
    resp = await admin_client.get(f"/api/projects/{proj['id']}")
    assert resp.status_code == 200
    assert resp.json()["description"] == "## Title\nBody text."


async def test_list_projects_includes_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescList", description="Listed desc")
    resp = await admin_client.get("/api/projects")
    assert resp.status_code == 200
    match = next((p for p in resp.json() if p["id"] == proj["id"]), None)
    assert match is not None
    assert match["description"] == "Listed desc"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def test_update_project_sets_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescUpdate")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}",
        json={"description": "New description"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "New description"


async def test_update_project_clears_description(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescClear", description="To be cleared")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}",
        json={"description": None},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] is None


async def test_update_project_omitting_description_leaves_it_unchanged(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescPreserve", description="Keep me")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}",
        json={"name": "DescPreserveRenamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Keep me"


async def test_update_project_description_too_long(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DescUpdateTooLong")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}",
        json={"description": "x" * 10_001},
    )
    assert resp.status_code == 422


async def test_update_project_description_non_admin_forbidden(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "DescUpdateForbidden", description="Original")
    username = unique_username("desc_non_admin")
    async with member_client(username) as c:
        resp = await c.patch(
            f"/api/projects/{proj['id']}",
            json={"description": "Hijacked"},
        )
        assert resp.status_code == 403

    # Description must be unchanged
    get_resp = await admin_client.get(f"/api/projects/{proj['id']}")
    assert get_resp.json()["description"] == "Original"
