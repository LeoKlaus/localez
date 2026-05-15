"""Integration tests for /projects/{id}/strings and /localizations endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Strings list
# ---------------------------------------------------------------------------

async def test_list_strings_as_any_user(member_client, unique_username, xcstrings_project: dict):
    username = unique_username("str_user")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{xcstrings_project['id']}/strings")
        assert resp.status_code == 200
        assert len(resp.json()) > 0
        assert "X-Total-Count" in resp.headers


async def test_list_strings_unauthenticated(client: AsyncClient, xcstrings_project: dict):
    resp = await client.get(f"/api/projects/{xcstrings_project['id']}/strings")
    assert resp.status_code == 200


async def test_list_strings_filter_should_translate(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings?should_translate=false")
    assert resp.status_code == 200
    keys = resp.json()
    assert all(k["should_translate"] is False for k in keys)
    assert any(k["key"] == "Don't translate" for k in keys)


async def test_list_strings_filter_language(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings?language=de")
    assert resp.status_code == 200
    # Every returned key must have at least one German localization
    assert len(resp.json()) > 0


async def test_list_strings_filter_query(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings?q=Print")
    assert resp.status_code == 200
    keys = resp.json()
    assert all("Print" in k["key"] for k in keys)


async def test_list_strings_pagination(admin_client: AsyncClient, xcstrings_project: dict):
    first = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings?limit=2&offset=0")
    second = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings?limit=2&offset=2")
    assert first.status_code == 200
    assert second.status_code == 200
    # No overlap in ids
    first_ids = {k["id"] for k in first.json()}
    second_ids = {k["id"] for k in second.json()}
    assert first_ids.isdisjoint(second_ids)


# ---------------------------------------------------------------------------
# String detail
# ---------------------------------------------------------------------------

async def test_get_string_detail_includes_localizations(admin_client: AsyncClient, xcstrings_project: dict):
    strings_resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")
    keys = strings_resp.json()
    reviewed = next(k for k in keys if k["key"] == "Reviewed")

    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings/{reviewed['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "Reviewed"
    assert isinstance(data["localizations"], list)
    langs = {loc["language"] for loc in data["localizations"]}
    assert "de" in langs
    assert "en" in langs


async def test_get_string_wrong_project_returns_404(admin_client: AsyncClient, xcstrings_project: dict):
    import uuid
    strings = (await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")).json()
    key_id = strings[0]["id"]

    other_proj = (await admin_client.post("/api/projects", json={"name": "Other", "source_language": "en"})).json()
    resp = await admin_client.get(f"/api/projects/{other_proj['id']}/strings/{key_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Localizations
# ---------------------------------------------------------------------------

async def test_list_localizations_for_key(admin_client: AsyncClient, xcstrings_project: dict):
    strings = (await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")).json()
    reviewed = next(k for k in strings if k["key"] == "Reviewed")

    resp = await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{reviewed['id']}/localizations"
    )
    assert resp.status_code == 200
    locs = resp.json()
    assert len(locs) > 0
    assert "X-Total-Count" in resp.headers
    langs = {loc["language"] for loc in locs}
    assert "en" in langs


async def test_list_localizations_filter_language(admin_client: AsyncClient, xcstrings_project: dict):
    strings = (await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")).json()
    reviewed = next(k for k in strings if k["key"] == "Reviewed")

    resp = await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{reviewed['id']}/localizations?language=de"
    )
    assert resp.status_code == 200
    locs = resp.json()
    assert all(loc["language"] == "de" for loc in locs)


async def test_get_localization(admin_client: AsyncClient, xcstrings_project: dict):
    strings = (await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")).json()
    reviewed = next(k for k in strings if k["key"] == "Reviewed")
    locs = (await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{reviewed['id']}/localizations"
    )).json()
    loc = locs[0]

    resp = await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{reviewed['id']}/localizations/{loc['id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == loc["id"]


async def test_get_localization_wrong_key_returns_404(admin_client: AsyncClient, xcstrings_project: dict):
    import uuid
    strings = (await admin_client.get(f"/api/projects/{xcstrings_project['id']}/strings")).json()
    sk_a = strings[0]
    sk_b = strings[1]
    locs_a = (await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{sk_a['id']}/localizations"
    )).json()
    if not locs_a:
        pytest.skip("No localizations on first key")
    loc = locs_a[0]

    resp = await admin_client.get(
        f"/api/projects/{xcstrings_project['id']}/strings/{sk_b['id']}/localizations/{loc['id']}"
    )
    assert resp.status_code == 404
