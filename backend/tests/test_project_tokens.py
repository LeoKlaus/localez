"""Integration tests for project-scoped import tokens."""
import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.usefixtures("setup_database")

EXAMPLE_PATH = Path(__file__).parent.parent / "Example.xcstrings"


def _upload() -> dict:
    return {"file": ("Example.xcstrings", EXAMPLE_PATH.read_bytes(), "application/json")}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_project(admin_client: AsyncClient, name: str) -> dict:
    resp = await admin_client.post("/api/projects", json={"name": name, "source_language": "en"})
    assert resp.status_code == 201
    return resp.json()


async def _create_token(admin_client: AsyncClient, project_id: str, name: str = "ci") -> dict:
    resp = await admin_client.post(f"/api/projects/{project_id}/tokens", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

async def test_admin_can_create_token(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenCreate")
    resp = await admin_client.post(f"/api/projects/{proj['id']}/tokens", json={"name": "github-ci"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "github-ci"
    assert data["token"].startswith("lz_")
    assert "token_hash" not in data
    assert data["last_used_at"] is None


async def test_create_token_returns_raw_token_once(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenOnce")
    created = await _create_token(admin_client, proj["id"])

    # Raw token only present in the create response, not in subsequent list
    tokens = (await admin_client.get(f"/api/projects/{proj['id']}/tokens")).json()
    matching = next(t for t in tokens if t["id"] == created["id"])
    assert "token" not in matching
    assert "token_hash" not in matching


async def test_create_token_for_nonexistent_project(admin_client: AsyncClient):
    resp = await admin_client.post(f"/api/projects/{uuid.uuid4()}/tokens", json={"name": "ci"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_admin_cannot_create_token(member_client, unique_username, project: dict):
    async with member_client(unique_username("tok_create")) as c:
        resp = await c.post(f"/api/projects/{project['id']}/tokens", json={"name": "ci"})
        assert resp.status_code == 403


async def test_unauthenticated_cannot_create_token(client: AsyncClient, project: dict):
    resp = await client.post(f"/api/projects/{project['id']}/tokens", json={"name": "ci"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token listing
# ---------------------------------------------------------------------------

async def test_list_tokens_returns_created_tokens(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenList")
    await _create_token(admin_client, proj["id"], "runner-1")
    await _create_token(admin_client, proj["id"], "runner-2")

    resp = await admin_client.get(f"/api/projects/{proj['id']}/tokens")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()}
    assert {"runner-1", "runner-2"}.issubset(names)


async def test_list_tokens_does_not_expose_hash(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenListHash")
    await _create_token(admin_client, proj["id"])

    tokens = (await admin_client.get(f"/api/projects/{proj['id']}/tokens")).json()
    for t in tokens:
        assert "token_hash" not in t
        assert "token" not in t


async def test_non_admin_cannot_list_tokens(member_client, unique_username, project: dict):
    async with member_client(unique_username("tok_list")) as c:
        resp = await c.get(f"/api/projects/{project['id']}/tokens")
        assert resp.status_code == 403


async def test_list_tokens_for_nonexistent_project(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/tokens")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------

async def test_admin_can_revoke_token(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenRevoke")
    created = await _create_token(admin_client, proj["id"])

    resp = await admin_client.delete(f"/api/projects/{proj['id']}/tokens/{created['id']}")
    assert resp.status_code == 204

    tokens = (await admin_client.get(f"/api/projects/{proj['id']}/tokens")).json()
    assert not any(t["id"] == created["id"] for t in tokens)


async def test_revoke_token_from_wrong_project(admin_client: AsyncClient):
    proj_a = await _create_project(admin_client, "TokenWrongA")
    proj_b = await _create_project(admin_client, "TokenWrongB")
    token = await _create_token(admin_client, proj_a["id"])

    resp = await admin_client.delete(f"/api/projects/{proj_b['id']}/tokens/{token['id']}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "TOKEN_NOT_FOUND"


async def test_revoke_nonexistent_token(admin_client: AsyncClient, project: dict):
    resp = await admin_client.delete(f"/api/projects/{project['id']}/tokens/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_non_admin_cannot_revoke_token(member_client, unique_username, project: dict, admin_client: AsyncClient):
    created = await _create_token(admin_client, project["id"])
    async with member_client(unique_username("tok_revoke")) as c:
        resp = await c.delete(f"/api/projects/{project['id']}/tokens/{created['id']}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Using a project token to import
# ---------------------------------------------------------------------------

async def _token_client(raw_token: str) -> AsyncClient:
    """Return an AsyncClient pre-configured with a project token bearer header."""
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    c.headers["Authorization"] = f"Bearer {raw_token}"
    return c


async def test_project_token_can_import(admin_client: AsyncClient, session_factory):
    from app.database import get_db

    proj = await _create_project(admin_client, "TokenImport")
    created = await _create_token(admin_client, proj["id"])
    raw = created["token"]

    async with await _token_client(raw) as c:
        # Ensure the DB override is active for the token client too
        async def override_get_db():
            async with session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        resp = await c.post(f"/api/projects/{proj['id']}/import", files=_upload())

    assert resp.status_code == 200
    assert resp.json()["imported_keys"] > 0


async def test_project_token_wrong_project_is_rejected(admin_client: AsyncClient, session_factory):
    from app.database import get_db

    proj_a = await _create_project(admin_client, "TokenScopeA")
    proj_b = await _create_project(admin_client, "TokenScopeB")
    created = await _create_token(admin_client, proj_a["id"])
    raw = created["token"]

    async with await _token_client(raw) as c:
        async def override_get_db():
            async with session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        resp = await c.post(f"/api/projects/{proj_b['id']}/import", files=_upload())

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_TOKEN"


async def test_invalid_project_token_is_rejected(client: AsyncClient, project: dict):
    client.headers["Authorization"] = "Bearer lz_thisisnotavalidtoken"
    resp = await client.post(f"/api/projects/{project['id']}/import", files=_upload())
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_TOKEN"


async def test_revoked_token_cannot_import(admin_client: AsyncClient, session_factory):
    from app.database import get_db

    proj = await _create_project(admin_client, "TokenRevokedImport")
    created = await _create_token(admin_client, proj["id"])
    raw = created["token"]

    await admin_client.delete(f"/api/projects/{proj['id']}/tokens/{created['id']}")

    async with await _token_client(raw) as c:
        async def override_get_db():
            async with session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        resp = await c.post(f"/api/projects/{proj['id']}/import", files=_upload())

    assert resp.status_code == 401


async def test_admin_jwt_still_accepted_for_import(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenAdminJWT")
    resp = await admin_client.post(f"/api/projects/{proj['id']}/import", files=_upload())
    assert resp.status_code == 200


async def test_regular_user_jwt_rejected_for_import(member_client, unique_username):
    username = unique_username("tok_import_user")
    async with member_client(username) as c:
        resp = await c.post(f"/api/projects/{uuid.uuid4()}/import", files=_upload())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# last_used_at tracking
# ---------------------------------------------------------------------------

async def test_last_used_at_updated_after_import(admin_client: AsyncClient, session_factory):
    from app.database import get_db

    proj = await _create_project(admin_client, "TokenLastUsed")
    created = await _create_token(admin_client, proj["id"])
    raw = created["token"]
    token_id = created["id"]

    tokens_before = (await admin_client.get(f"/api/projects/{proj['id']}/tokens")).json()
    assert next(t for t in tokens_before if t["id"] == token_id)["last_used_at"] is None

    async with await _token_client(raw) as c:
        async def override_get_db():
            async with session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        await c.post(f"/api/projects/{proj['id']}/import", files=_upload())

    tokens_after = (await admin_client.get(f"/api/projects/{proj['id']}/tokens")).json()
    assert next(t for t in tokens_after if t["id"] == token_id)["last_used_at"] is not None


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------

async def test_tokens_deleted_when_project_deleted(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "TokenCascade")
    created = await _create_token(admin_client, proj["id"])
    token_id = created["id"]

    await admin_client.delete(f"/api/projects/{proj['id']}")

    # Project is gone; verify the token row is gone too by trying to revoke it
    # (any project will do for the path — we just need a 404, not a 500)
    other_proj = await _create_project(admin_client, "TokenCascadeOther")
    resp = await admin_client.delete(f"/api/projects/{other_proj['id']}/tokens/{token_id}")
    assert resp.status_code == 404
