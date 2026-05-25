"""Additional integration tests for /projects."""
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

async def test_list_projects_admin_sees_all(admin_client: AsyncClient):
    await admin_client.post("/api/projects", json={"name": "ListAll A", "source_language": "en"})
    await admin_client.post("/api/projects", json={"name": "ListAll B", "source_language": "fr"})

    resp = await admin_client.get("/api/projects")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    names = [p["name"] for p in resp.json()]
    assert "ListAll A" in names
    assert "ListAll B" in names


async def test_list_projects_non_member_sees_only_public(
    admin_client: AsyncClient, member_client, unique_username
):
    # Public projects are visible; private ones are not
    await admin_client.post("/api/projects", json={"name": "Public Project Visible", "source_language": "en", "is_public": True})
    await admin_client.post("/api/projects", json={"name": "Private Project Hidden", "source_language": "en"})

    username = unique_username("listpub")
    async with member_client(username) as c:
        resp = await c.get("/api/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Public Project Visible" in names
        assert "Private Project Hidden" not in names


async def test_list_projects_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/projects")
    assert resp.status_code == 200


async def test_get_project_as_admin(admin_client: AsyncClient, project: dict):
    resp = await admin_client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


async def test_non_member_cannot_get_private_project(member_client, unique_username, project: dict):
    username = unique_username("getuser")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 403


async def test_get_project_not_found(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_update_project(admin_client: AsyncClient, project: dict):
    resp = await admin_client.patch(f"/api/projects/{project['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_update_project_source_language(admin_client: AsyncClient, project: dict):
    resp = await admin_client.patch(f"/api/projects/{project['id']}", json={"source_language": "fr"})
    assert resp.status_code == 200
    assert resp.json()["source_language"] == "fr"


async def test_update_project_non_admin_gets_403(member_client, unique_username, project: dict):
    username = unique_username("noupdate")
    async with member_client(username) as c:
        resp = await c.patch(f"/api/projects/{project['id']}", json={"name": "Should fail"})
        assert resp.status_code == 403


async def test_delete_project(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "To Delete", "source_language": "en"})).json()
    resp = await admin_client.delete(f"/api/projects/{proj['id']}")
    assert resp.status_code == 204

    get_resp = await admin_client.get(f"/api/projects/{proj['id']}")
    assert get_resp.status_code == 404


async def test_delete_project_non_admin_gets_403(member_client, unique_username, project: dict):
    username = unique_username("nodelete")
    async with member_client(username) as c:
        resp = await c.delete(f"/api/projects/{project['id']}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Language management
# ---------------------------------------------------------------------------

async def test_project_response_includes_languages(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangTest", "source_language": "en"})).json()
    assert "languages" in proj
    assert proj["languages"] == []


async def test_add_language_to_project(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangAdd", "source_language": "en"})).json()

    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    assert resp.status_code == 201
    assert "de" in resp.json()["languages"]


async def test_add_multiple_languages(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangMulti", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "fr"})

    resp = await admin_client.get(f"/api/projects/{proj['id']}")
    assert resp.status_code == 200
    assert set(resp.json()["languages"]) == {"de", "fr"}


async def test_add_duplicate_language_returns_409(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangDup", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})

    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LANGUAGE_ALREADY_EXISTS"


async def test_add_invalid_language_code_returns_422(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangInvalid", "source_language": "en"})).json()

    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "not-a-valid-!!-code"})
    assert resp.status_code == 422


async def test_remove_language_from_project(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangRemove", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})

    resp = await admin_client.delete(f"/api/projects/{proj['id']}/languages/de")
    assert resp.status_code == 204

    updated = (await admin_client.get(f"/api/projects/{proj['id']}")).json()
    assert "de" not in updated["languages"]


async def test_remove_nonexistent_language_returns_404(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "LangRemove404", "source_language": "en"})).json()

    resp = await admin_client.delete(f"/api/projects/{proj['id']}/languages/de")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


async def test_add_language_requires_auth(client: AsyncClient):
    resp = await client.post(f"/api/projects/{uuid.uuid4()}/languages", json={"language": "de"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

async def test_stats_empty_project(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "StatsEmpty", "source_language": "en"})).json()

    resp = await admin_client.get(f"/api/projects/{proj['id']}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_strings"] == 0
    assert body["languages"] == []


async def test_stats_after_import(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/stats")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_strings"] > 0
    assert len(body["languages"]) > 0

    for lang in body["languages"]:
        assert "language" in lang
        assert "translated" in lang
        assert "needs_review" in lang
        assert "missing" in lang
        assert lang["translated"] + lang["needs_review"] + lang["missing"] == body["total_strings"]


async def test_stats_counts_match_total(admin_client: AsyncClient):
    """Each language's (translated + needs_review + missing) must equal total_strings."""
    proj = (await admin_client.post("/api/projects", json={"name": "StatsCount", "source_language": "en"})).json()
    example = Path(__file__).parent.parent / "Example.xcstrings"
    await admin_client.post(
        f"/api/projects/{proj['id']}/import",
        files={"file": (example.name, example.read_bytes(), "application/json")},
    )

    resp = await admin_client.get(f"/api/projects/{proj['id']}/stats")
    assert resp.status_code == 200
    body = resp.json()

    for lang in body["languages"]:
        total = lang["translated"] + lang["needs_review"] + lang["missing"]
        assert total == body["total_strings"], f"Language {lang['language']}: {total} != {body['total_strings']}"


async def test_stats_not_found(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/stats")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_member_cannot_access_private_project_stats(member_client, unique_username, project: dict):
    username = unique_username("stats_user")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{project['id']}/stats")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Language localizations
# ---------------------------------------------------------------------------

async def test_language_localizations_after_import(admin_client: AsyncClient, xcstrings_project: dict):
    proj_id = xcstrings_project["id"]
    proj = (await admin_client.get(f"/api/projects/{proj_id}")).json()
    lang = proj["languages"][0]

    resp = await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers

    items = resp.json()
    assert len(items) > 0
    for item in items:
        assert item["language"] == lang
        assert "key" in item
        assert "string_key_id" in item
        assert "state" in item
        assert "value" in item or item.get("value") is None


async def test_language_localizations_state_filter(admin_client: AsyncClient, xcstrings_project: dict):
    proj_id = xcstrings_project["id"]
    proj = (await admin_client.get(f"/api/projects/{proj_id}")).json()
    lang = proj["languages"][0]

    resp = await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations?state=translated")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "translated"


async def test_language_localizations_invalid_state(admin_client: AsyncClient, xcstrings_project: dict):
    proj_id = xcstrings_project["id"]
    proj = (await admin_client.get(f"/api/projects/{proj_id}")).json()
    lang = proj["languages"][0]

    resp = await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations?state=bogus")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_STATE"


async def test_language_localizations_unknown_language(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/languages/zz/localizations")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


async def test_non_member_cannot_access_private_language_localizations(member_client, unique_username, xcstrings_project: dict):
    username = unique_username("loclang_user")
    proj_id = xcstrings_project["id"]
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{proj_id}/languages/en/localizations")
        assert resp.status_code == 403


async def test_language_localizations_pagination(admin_client: AsyncClient, xcstrings_project: dict):
    proj_id = xcstrings_project["id"]
    proj = (await admin_client.get(f"/api/projects/{proj_id}")).json()
    lang = proj["languages"][0]

    total = int((await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations")).headers["X-Total-Count"])
    page = (await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations?limit=2&offset=0")).json()
    assert len(page) <= 2
    assert int((await admin_client.get(f"/api/projects/{proj_id}/languages/{lang}/localizations?limit=2&offset=0")).headers["X-Total-Count"]) == total
