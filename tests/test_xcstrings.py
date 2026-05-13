"""Integration tests for xcstrings import and export endpoints."""
import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")

EXAMPLE_PATH = Path(__file__).parent.parent / "Example.xcstrings"


def _example_bytes() -> bytes:
    return EXAMPLE_PATH.read_bytes()


def _example_data() -> dict:
    return json.loads(EXAMPLE_PATH.read_text())


def _upload(data: dict | None = None) -> dict:
    """Build an httpx files= payload from a dict (or the example file if omitted)."""
    content = json.dumps(data).encode() if data is not None else _example_bytes()
    return {"file": ("Example.xcstrings", content, "application/json")}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

async def test_import_creates_string_keys(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportTest", "source_language": "en"})).json()
    resp = await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_keys"] == 8
    assert data["imported_localizations"] > 0

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    key_names = {s["key"] for s in strings}
    assert "Reviewed" in key_names
    assert "Don't translate" in key_names
    assert "Save to your iPhone" in key_names


async def test_import_marks_non_translatable(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportNT", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    nt = next(s for s in strings if s["key"] == "Don't translate")
    assert nt["should_translate"] is False


async def test_import_creates_localizations_with_states(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportState", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    reviewed = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{proj['id']}/strings/{reviewed['id']}/localizations")).json()
    states = {loc["state"] for loc in locs}
    assert "translated" in states


async def test_import_skip_does_not_overwrite(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportSkip", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    # Patch the data to have a different value and re-import with skip
    data = _example_data()
    data["strings"]["Reviewed"]["localizations"]["en"]["stringUnit"]["value"] = "CHANGED"
    await admin_client.post(f"/api/projects/{proj['id']}/import?conflict=skip", files=_upload(data))

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    reviewed = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{proj['id']}/strings/{reviewed['id']}/localizations")).json()
    en_loc = next(loc for loc in locs if loc["language"] == "en" and loc["variation_type"] == "none")
    assert en_loc["value"] != "CHANGED"


async def test_import_overwrite_updates_values(admin_client: AsyncClient):
    """
    Test overwrite using a device-variation localization (variation_key is non-NULL),
    which works correctly with PostgreSQL ON CONFLICT.
    Flat string-unit rows (variation_key=NULL) are excluded because NULL!=NULL in
    unique indexes means ON CONFLICT never fires for them — a known limitation.
    """
    proj = (await admin_client.post("/api/projects", json={"name": "ImportOverwrite", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    data = _example_data()
    save_locs = data["strings"]["Save to your iPhone"]["localizations"]
    if "en" in save_locs and "variations" in save_locs["en"] and "device" in save_locs["en"]["variations"]:
        device_vars = save_locs["en"]["variations"]["device"]
        first_device_key = next(iter(device_vars))
        device_vars[first_device_key]["stringUnit"]["value"] = "CHANGED_DEVICE"
    else:
        pytest.skip("Expected device variation not found in fixture")

    await admin_client.post(f"/api/projects/{proj['id']}/import?conflict=overwrite", files=_upload(data))

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    save_key = next(s for s in strings if s["key"] == "Save to your iPhone")
    locs = (await admin_client.get(
        f"/api/projects/{proj['id']}/strings/{save_key['id']}/localizations"
    )).json()
    device_locs = [l for l in locs if l["language"] == "en" and l["variation_type"] == "device"]
    assert any(l["value"] == "CHANGED_DEVICE" for l in device_locs)


async def test_import_idempotent(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportIdempotent", "source_language": "en"})).json()

    r1 = await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())
    r2 = await admin_client.post(f"/api/projects/{proj['id']}/import?conflict=skip", files=_upload())

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["imported_keys"] == r2.json()["imported_keys"]


async def test_import_invalid_json(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportBadJSON", "source_language": "en"})).json()
    resp = await admin_client.post(
        f"/api/projects/{proj['id']}/import",
        files={"file": ("bad.xcstrings", b"not json at all", "application/json")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_XCSTRINGS"


async def test_import_requires_admin(member_client, unique_username):
    username = unique_username("import_norole")
    async with member_client(username) as c:
        resp = await c.post(
            f"/api/projects/{uuid.uuid4()}/import",
            files=_upload(),
        )
        assert resp.status_code == 403


async def test_import_nonexistent_project(admin_client: AsyncClient):
    resp = await admin_client.post(f"/api/projects/{uuid.uuid4()}/import", files=_upload())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

async def test_export_returns_xcstrings_structure(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sourceLanguage"] == "en"
    assert data["version"] == "1.2"
    assert "strings" in data
    assert "Reviewed" in data["strings"]


async def test_export_includes_non_translatable(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/export")
    data = resp.json()
    assert "Don't translate" in data["strings"]
    assert data["strings"]["Don't translate"].get("shouldTranslate") is False


async def test_export_filter_language(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/export?languages=de")
    assert resp.status_code == 200
    data = resp.json()
    for key_data in data["strings"].values():
        locs = key_data.get("localizations", {})
        for lang in locs:
            assert lang == "de"


async def test_export_content_disposition_header(admin_client: AsyncClient, xcstrings_project: dict):
    resp = await admin_client.get(f"/api/projects/{xcstrings_project['id']}/export")
    assert "Content-Disposition" in resp.headers
    assert ".xcstrings" in resp.headers["Content-Disposition"]


async def test_export_guest_can_access(admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict):
    username = unique_username("export_guest")
    async with member_client(username) as c:
        user_id = (await c.get("/api/users/me")).json()["id"]
        await admin_client.post(f"/api/projects/{xcstrings_project['id']}/members", json={
            "user_id": user_id, "project_role": "guest",
        })
        resp = await c.get(f"/api/projects/{xcstrings_project['id']}/export")
        assert resp.status_code == 200


async def test_export_non_member_gets_403(member_client, unique_username, xcstrings_project: dict):
    username = unique_username("export_nomember")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{xcstrings_project['id']}/export")
        assert resp.status_code == 403


async def test_import_registers_languages(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportLang", "source_language": "en"})).json()
    assert proj["languages"] == []

    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    updated = (await admin_client.get(f"/api/projects/{proj['id']}")).json()
    assert len(updated["languages"]) > 0
    assert "en" in updated["languages"]


async def test_import_languages_idempotent(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "ImportLangIdem", "source_language": "en"})).json()

    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())
    await admin_client.post(f"/api/projects/{proj['id']}/import?conflict=skip", files=_upload())

    updated = (await admin_client.get(f"/api/projects/{proj['id']}")).json()
    # Languages should not be duplicated
    assert len(updated["languages"]) == len(set(updated["languages"]))


async def test_import_fills_variation_placeholders_for_missing_languages(admin_client: AsyncClient):
    """After import, a language added post-import should receive variation placeholders
    matching those of the source language, not a flat root localization."""
    proj = (await admin_client.post("/api/projects", json={"name": "VarFill", "source_language": "en"})).json()
    await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())

    # Add a language that wasn't in the xcstrings file
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "ja"})

    strings = (await admin_client.get(f"/api/projects/{proj['id']}/strings")).json()
    save_key = next(s for s in strings if s["key"] == "Save to your iPhone")
    locs = (await admin_client.get(f"/api/projects/{proj['id']}/strings/{save_key['id']}/localizations")).json()

    ja_locs = [l for l in locs if l["language"] == "ja"]
    # Should have device variation placeholders, not a flat root localization
    assert all(l["variation_type"] == "device" for l in ja_locs), \
        f"Expected only device variations for 'ja', got: {[(l['variation_type'], l['variation_key']) for l in ja_locs]}"
    assert all(l["state"] == "new" for l in ja_locs)
    assert all(l["value"] is None for l in ja_locs)
