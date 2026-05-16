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


# ---------------------------------------------------------------------------
# Set localization value
# ---------------------------------------------------------------------------

async def _first_new_localization(admin_client, xcstrings_project):
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    for sk in strings:
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{sk['id']}/localizations")).json()
        for loc in locs:
            if loc["state"] == "new":
                return sk["id"], loc["id"]
    return None, None


async def test_any_user_can_set_initial_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("sv_user")
    async with member_client(username) as c:
        key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
        assert loc_id is not None, "No 'new' localization found"
        resp = await c.put(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Erste Übersetzung"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "Erste Übersetzung"
        assert data["state"] == "needs_review"


async def test_non_admin_cannot_override_existing_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated")

    username = unique_username("sv_nooverride")
    async with member_client(username) as c:
        resp = await c.put(
            f"/api/projects/{pid}/strings/{key['id']}/localizations/{loc['id']}/value",
            json={"value": "Überschrieben"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "VALUE_ALREADY_SET"


async def test_admin_can_override_existing_value(
    admin_client: AsyncClient, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated")

    resp = await admin_client.put(
        f"/api/projects/{pid}/strings/{key['id']}/localizations/{loc['id']}/value",
        json={"value": "Admin-Überschreibung"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == "Admin-Überschreibung"
    assert data["state"] == "needs_review"


async def test_unauthenticated_cannot_set_value(
    admin_client: AsyncClient, client: AsyncClient, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
    assert loc_id is not None
    resp = await client.put(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
        json={"value": "Anonym"},
    )
    assert resp.status_code == 401


async def test_original_author_can_override_own_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("sv_author")
    async with member_client(username) as c:
        key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
        assert loc_id is not None, "No 'new' localization found"

        await c.put(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Erster Wert"},
        )
        resp = await c.put(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Aktualisierter Wert"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "Aktualisierter Wert"


async def test_different_user_cannot_override_others_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    author = unique_username("sv_author2")
    intruder = unique_username("sv_intruder")

    async with member_client(author) as c:
        key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
        assert loc_id is not None, "No 'new' localization found"
        await c.put(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Gesetzt von Autor"},
        )

    async with member_client(intruder) as c:
        resp = await c.put(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Überschreiben versucht"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "VALUE_ALREADY_SET"
