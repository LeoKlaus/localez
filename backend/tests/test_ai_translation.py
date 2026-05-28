"""Test for AI-powered endpoints (prefill, back-translate)"""
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")

# ---------------------------------------------------------------------------
# Prefill — no provider configured
# ---------------------------------------------------------------------------

async def test_prefill_returns_400_when_no_provider_configured(admin_client: AsyncClient, xcstrings_project: dict):
    """The test environment has no API keys, so prefill_provider is None."""
    pid = xcstrings_project["id"]
    resp = await admin_client.post(f"/api/projects/{pid}/languages/de/prefill")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_prefill_returns_404_for_unknown_language(admin_client: AsyncClient, xcstrings_project: dict):
    pid = xcstrings_project["id"]
    resp = await admin_client.post(f"/api/projects/{pid}/languages/zz/prefill")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


async def test_prefill_requires_admin(member_client, unique_username, xcstrings_project: dict):
    pid = xcstrings_project["id"]
    username = unique_username("prefill_user")
    async with member_client(username) as c:
        resp = await c.post(f"/api/projects/{pid}/languages/de/prefill")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Back-translate localization — mocked provider
# ---------------------------------------------------------------------------

async def test_back_translate_localization_returns_422_when_no_provider(
    admin_client: AsyncClient, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    # Fetch a translated localization
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated")

    resp = await admin_client.post(f"/api/projects/{pid}/localizations/{loc['id']}/back-translate")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_back_translate_localization_happy_path(admin_client: AsyncClient, xcstrings_project: dict):
    from unittest.mock import AsyncMock, MagicMock, patch

    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated" and l["value"])

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.projects.settings", mock_settings), \
         patch("app.routers.projects.translation_service.prefill", new=AsyncMock(return_value=["Back-translated"])):
        resp = await admin_client.post(f"/api/projects/{pid}/localizations/{loc['id']}/back-translate")

    assert resp.status_code == 200
    assert resp.json()["text"] == "Back-translated"


async def test_back_translate_localization_not_found(admin_client: AsyncClient):
    from unittest.mock import MagicMock, patch

    proj = (await admin_client.post("/api/projects", json={"name": "BT404", "source_language": "en"})).json()
    pid = proj["id"]

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.projects.settings", mock_settings):
        resp = await admin_client.post(f"/api/projects/{pid}/localizations/{uuid.uuid4()}/back-translate")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


async def test_back_translate_localization_no_value(admin_client: AsyncClient, xcstrings_project: dict):
    from unittest.mock import MagicMock, patch

    pid = xcstrings_project["id"]
    # Find any new, empty localization across all string keys
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    new_loc = None
    for sk in strings:
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{sk['id']}/localizations")).json()
        new_loc = next((l for l in locs if l["state"] == "new" and l["value"] is None), None)
        if new_loc:
            break
    assert new_loc is not None, "No new empty localization found in xcstrings_project"

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.projects.settings", mock_settings):
        resp = await admin_client.post(f"/api/projects/{pid}/localizations/{new_loc['id']}/back-translate")

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "NO_VALUE"


# ---------------------------------------------------------------------------
# Back-translate proposal — mocked provider
# ---------------------------------------------------------------------------

async def test_back_translate_proposal_returns_422_when_no_provider(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated" and l["value"])

    username = unique_username("bt_prop_noprov")
    async with member_client(username) as c:
        await admin_client.post(f"/api/projects/{pid}/members", json={"username": username})
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key['id']}/localizations/{loc['id']}/proposals",
            json={"proposed_value": "Vorschlag", "comment": "test"},
        )).json()

    resp = await admin_client.post(f"/api/projects/{pid}/proposals/{prop['id']}/back-translate")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "PROVIDER_NOT_CONFIGURED"


async def test_back_translate_proposal_happy_path(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    from unittest.mock import AsyncMock, MagicMock, patch

    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(l for l in locs if l["state"] == "translated" and l["value"])

    username = unique_username("bt_prop_ok")
    async with member_client(username) as c:
        await admin_client.post(f"/api/projects/{pid}/members", json={"username": username})
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key['id']}/localizations/{loc['id']}/proposals",
            json={"proposed_value": "Ein Vorschlag", "comment": "test"},
        )).json()

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.projects.settings", mock_settings), \
         patch("app.routers.projects.translation_service.prefill", new=AsyncMock(return_value=["A proposal"])):
        resp = await admin_client.post(f"/api/projects/{pid}/proposals/{prop['id']}/back-translate")

    assert resp.status_code == 200
    assert resp.json()["text"] == "A proposal"


async def test_back_translate_proposal_not_found(admin_client: AsyncClient):
    from unittest.mock import MagicMock, patch

    proj = (await admin_client.post("/api/projects", json={"name": "BTProp404", "source_language": "en"})).json()
    pid = proj["id"]

    mock_settings = MagicMock()
    mock_settings.prefill_provider = "deepl"
    with patch("app.routers.projects.settings", mock_settings):
        resp = await admin_client.post(f"/api/projects/{pid}/proposals/{uuid.uuid4()}/back-translate")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"
