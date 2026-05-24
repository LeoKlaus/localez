"""Tests for project icon management."""
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_png() -> bytes:
    """Return a minimal 1×1 red PNG as bytes (no PIL dependency)."""
    # Pre-built 1×1 pixel red PNG binary (standard IDAT chunk)
    import zlib, struct

    def _chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    # RGB pixel (255, 0, 0) with filter byte 0
    raw = b"\x00\xff\x00\x00"
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Icon upload (PUT /{project_id}/icon)
# ---------------------------------------------------------------------------

async def test_admin_can_upload_icon(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconUpload", "source_language": "en"})).json()
    pid = proj["id"]

    resp = await admin_client.put(
        f"/api/projects/{pid}/icon",
        files={"file": ("icon.png", _minimal_png(), "image/png")},
    )
    assert resp.status_code == 204


async def test_non_admin_cannot_upload_icon(member_client, unique_username, admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconNoUpload", "source_language": "en"})).json()
    pid = proj["id"]

    username = unique_username("icon_user")
    async with member_client(username) as c:
        resp = await c.put(
            f"/api/projects/{pid}/icon",
            files={"file": ("icon.png", _minimal_png(), "image/png")},
        )
        assert resp.status_code == 403


async def test_upload_invalid_image_returns_422(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconBad", "source_language": "en"})).json()
    pid = proj["id"]

    resp = await admin_client.put(
        f"/api/projects/{pid}/icon",
        files={"file": ("notanimage.txt", b"not an image at all", "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_IMAGE"


async def test_upload_icon_for_nonexistent_project(admin_client: AsyncClient):
    resp = await admin_client.put(
        f"/api/projects/{uuid.uuid4()}/icon",
        files={"file": ("icon.png", _minimal_png(), "image/png")},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Icon retrieval (GET /{project_id}/icon)
# ---------------------------------------------------------------------------

async def test_get_icon_after_upload(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconGet", "source_language": "en"})).json()
    pid = proj["id"]

    await admin_client.put(
        f"/api/projects/{pid}/icon",
        files={"file": ("icon.png", _minimal_png(), "image/png")},
    )
    resp = await admin_client.get(f"/api/projects/{pid}/icon")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


async def test_get_icon_no_icon_returns_404(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconGetNone", "source_language": "en"})).json()
    pid = proj["id"]

    resp = await admin_client.get(f"/api/projects/{pid}/icon")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ICON_NOT_FOUND"


async def test_get_icon_nonexistent_project_returns_404(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/icon")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Icon deletion (DELETE /{project_id}/icon)
# ---------------------------------------------------------------------------

async def test_admin_can_delete_icon(admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconDel", "source_language": "en"})).json()
    pid = proj["id"]

    await admin_client.put(
        f"/api/projects/{pid}/icon",
        files={"file": ("icon.png", _minimal_png(), "image/png")},
    )
    resp = await admin_client.delete(f"/api/projects/{pid}/icon")
    assert resp.status_code == 204

    # Icon should no longer be retrievable
    get_resp = await admin_client.get(f"/api/projects/{pid}/icon")
    assert get_resp.status_code == 404


async def test_delete_icon_for_nonexistent_project(admin_client: AsyncClient):
    resp = await admin_client.delete(f"/api/projects/{uuid.uuid4()}/icon")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_admin_cannot_delete_icon(member_client, unique_username, admin_client: AsyncClient):
    proj = (await admin_client.post("/api/projects", json={"name": "IconDelNoAuth", "source_language": "en"})).json()
    pid = proj["id"]

    await admin_client.put(
        f"/api/projects/{pid}/icon",
        files={"file": ("icon.png", _minimal_png(), "image/png")},
    )
    username = unique_username("icon_del_user")
    async with member_client(username) as c:
        resp = await c.delete(f"/api/projects/{pid}/icon")
        assert resp.status_code == 403
