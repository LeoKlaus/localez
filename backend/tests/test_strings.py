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
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()

    # Find two distinct keys that each have at least one localization.
    keys_with_locs = []
    for sk in strings:
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{sk['id']}/localizations")).json()
        if locs:
            keys_with_locs.append((sk, locs))
        if len(keys_with_locs) == 2:
            break

    assert len(keys_with_locs) >= 2, "Need at least two translatable string keys"
    (sk_a, locs_a), (sk_b, _) = keys_with_locs

    resp = await admin_client.get(
        f"/api/projects/{pid}/strings/{sk_b['id']}/localizations/{locs_a[0]['id']}"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _find_localization(admin_client, xcstrings_project, *, state, language=None):
    """Return (key_id, loc_id, loc) for the first localization matching state."""
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    for sk in strings:
        url = f"/api/projects/{pid}/strings/{sk['id']}/localizations"
        if language:
            url += f"?language={language}"
        for loc in (await admin_client.get(url)).json():
            if loc["state"] == state:
                return sk["id"], loc["id"], loc
    return None, None, None


async def _first_new_empty_localization(admin_client, xcstrings_project, language="de"):
    """Return (key_id, loc_id) for a new, valueless localization in the given language."""
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    for sk in strings:
        locs = (await admin_client.get(
            f"/api/projects/{pid}/strings/{sk['id']}/localizations?language={language}"
        )).json()
        for loc in locs:
            if loc["state"] == "new" and loc["value"] is None:
                return sk["id"], loc["id"]
    return None, None


# ---------------------------------------------------------------------------
# update_localization_state
# ---------------------------------------------------------------------------

async def test_admin_can_set_state_to_translated(admin_client: AsyncClient, xcstrings_project: dict):
    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _find_localization(admin_client, xcstrings_project, state="needs_review")
    assert loc_id is not None, "No needs_review localization found"

    resp = await admin_client.patch(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/state",
        json={"state": "translated"},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "translated"


async def test_admin_can_set_state_to_new_clears_value(admin_client: AsyncClient, xcstrings_project: dict):
    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _find_localization(admin_client, xcstrings_project, state="translated")
    assert loc_id is not None, "No translated localization found"

    resp = await admin_client.patch(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/state",
        json={"state": "new"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "new"
    assert data["value"] is None
    assert data["value_set_by"] is None


async def test_non_admin_cannot_update_state(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _find_localization(admin_client, xcstrings_project, state="needs_review")
    assert loc_id is not None

    async with member_client(unique_username("state_user")) as c:
        resp = await c.patch(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/state",
            json={"state": "translated"},
        )
        assert resp.status_code == 403


async def test_update_state_wrong_project_returns_404(admin_client: AsyncClient, xcstrings_project: dict):
    import uuid
    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _find_localization(admin_client, xcstrings_project, state="needs_review")
    assert loc_id is not None

    resp = await admin_client.patch(
        f"/api/projects/{uuid.uuid4()}/strings/{key_id}/localizations/{loc_id}/state",
        json={"state": "translated"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# suggest_localization
# ---------------------------------------------------------------------------

async def test_suggest_returns_422_when_no_provider(admin_client: AsyncClient, xcstrings_project: dict):
    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_empty_localization(admin_client, xcstrings_project)
    assert loc_id is not None, "No new empty localization found"

    # Test environment has no API keys, so prefill_provider is None
    resp = await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_suggest_returns_409_when_localization_has_value(admin_client: AsyncClient, xcstrings_project: dict):
    from unittest.mock import MagicMock, patch

    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _find_localization(admin_client, xcstrings_project, state="translated")
    assert loc_id is not None

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.strings.settings", mock_settings):
        resp = await admin_client.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NOT_EMPTY"


async def test_suggest_returns_409_when_suggestion_already_exists(
    admin_client: AsyncClient, xcstrings_project: dict
):
    from unittest.mock import AsyncMock, MagicMock, patch

    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_empty_localization(admin_client, xcstrings_project)
    assert loc_id is not None

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.strings.settings", mock_settings), \
         patch("app.routers.strings.translation_service.prefill", new=AsyncMock(return_value=["Erster Vorschlag"])):
        await admin_client.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
        resp = await admin_client.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "SUGGESTION_EXISTS"


async def test_suggest_happy_path_returns_localization_with_key(
    admin_client: AsyncClient, xcstrings_project: dict
):
    from unittest.mock import AsyncMock, MagicMock, patch

    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_empty_localization(admin_client, xcstrings_project)
    assert loc_id is not None

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.strings.settings", mock_settings), \
         patch("app.routers.strings.translation_service.prefill", new=AsyncMock(return_value=["Hallo Welt"])):
        resp = await admin_client.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == loc_id
    assert data["ai_suggestion"] == "Hallo Welt"
    assert "key" in data
    assert "source_value" in data


async def test_suggest_returns_502_on_translation_error(
    admin_client: AsyncClient, xcstrings_project: dict
):
    from unittest.mock import AsyncMock, MagicMock, patch

    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_empty_localization(admin_client, xcstrings_project)
    assert loc_id is not None

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.strings.settings", mock_settings), \
         patch("app.routers.strings.translation_service.prefill", new=AsyncMock(side_effect=RuntimeError("API down"))):
        resp = await admin_client.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "TRANSLATION_ERROR"


async def test_suggest_unauthenticated_returns_401(client: AsyncClient, xcstrings_project: dict):
    import uuid
    pid = xcstrings_project["id"]
    resp = await client.post(
        f"/api/projects/{pid}/strings/{uuid.uuid4()}/localizations/{uuid.uuid4()}/suggest"
    )
    assert resp.status_code == 401


async def test_suggest_returns_404_for_wrong_project(admin_client: AsyncClient, xcstrings_project: dict):
    import uuid
    from unittest.mock import MagicMock, patch

    pid = xcstrings_project["id"]
    key_id, loc_id = await _first_new_empty_localization(admin_client, xcstrings_project)
    assert loc_id is not None

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.strings.settings", mock_settings):
        resp = await admin_client.post(
            f"/api/projects/{uuid.uuid4()}/strings/{key_id}/localizations/{loc_id}/suggest"
        )
    assert resp.status_code == 404
