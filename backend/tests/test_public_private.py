"""Integration tests for public/private project access control."""
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")

_XCSTRINGS_PATH = Path(__file__).parent.parent / "Example.xcstrings"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_project(admin_client: AsyncClient, name: str, *, is_public: bool = False) -> dict:
    resp = await admin_client.post(
        "/api/projects",
        json={"name": name, "source_language": "en", "is_public": is_public},
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup_project_with_strings(
    admin_client: AsyncClient, name: str, *, is_public: bool = False
) -> dict:
    """Create a project, import xcstrings (which adds 'de' language with localizations)."""
    proj = await _create_project(admin_client, name, is_public=is_public)
    imp = await admin_client.post(
        f"/api/projects/{proj['id']}/import",
        files={"file": (_XCSTRINGS_PATH.name, _XCSTRINGS_PATH.read_bytes(), "application/json")},
    )
    assert imp.status_code == 200
    return proj


# ---------------------------------------------------------------------------
# ProjectResponse includes is_public
# ---------------------------------------------------------------------------

async def test_project_response_includes_is_public(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "IsPublicField")
    assert "is_public" in proj
    assert proj["is_public"] is False


async def test_create_public_project(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "CreatePublic", is_public=True)
    assert proj["is_public"] is True


async def test_update_project_can_set_is_public(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "SetPublic")
    assert proj["is_public"] is False

    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}", json={"is_public": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is True


async def test_update_project_can_unset_is_public(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "UnsetPublic", is_public=True)
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}", json={"is_public": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is False


# ---------------------------------------------------------------------------
# list_projects access control
# ---------------------------------------------------------------------------

async def test_unauthenticated_sees_only_public_in_list(admin_client: AsyncClient, client: AsyncClient):
    pub = await _create_project(admin_client, "ListPub_Unauth", is_public=True)
    priv = await _create_project(admin_client, "ListPriv_Unauth")

    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert pub["id"] in ids
    assert priv["id"] not in ids


async def test_non_member_sees_only_public_in_list(
    admin_client: AsyncClient, member_client, unique_username
):
    pub = await _create_project(admin_client, "ListPub_NM", is_public=True)
    priv = await _create_project(admin_client, "ListPriv_NM")

    username = unique_username("listview_nm")
    async with member_client(username) as c:
        resp = await c.get("/api/projects")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert pub["id"] in ids
        assert priv["id"] not in ids


async def test_member_sees_their_private_project_in_list(
    admin_client: AsyncClient, member_client, unique_username
):
    priv = await _create_project(admin_client, "ListPriv_Member")
    username = unique_username("listview_member")
    async with member_client(username) as c:
        await admin_client.post(
            f"/api/projects/{priv['id']}/members", json={"username": username}
        )
        resp = await c.get("/api/projects")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert priv["id"] in ids


async def test_global_admin_sees_all_in_list(admin_client: AsyncClient):
    pub = await _create_project(admin_client, "ListAll_Pub", is_public=True)
    priv = await _create_project(admin_client, "ListAll_Priv")

    resp = await admin_client.get("/api/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert pub["id"] in ids
    assert priv["id"] in ids


# ---------------------------------------------------------------------------
# get_project access control
# ---------------------------------------------------------------------------

async def test_unauthenticated_can_get_public_project(admin_client: AsyncClient, client: AsyncClient):
    proj = await _create_project(admin_client, "GetPub_Unauth", is_public=True)
    resp = await client.get(f"/api/projects/{proj['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == proj["id"]


async def test_non_member_can_get_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "GetPub_NM", is_public=True)
    username = unique_username("getpub_nm")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{proj['id']}")
        assert resp.status_code == 200


async def test_unauthenticated_cannot_get_private_project(admin_client: AsyncClient, client: AsyncClient):
    proj = await _create_project(admin_client, "GetPriv_Unauth")
    resp = await client.get(f"/api/projects/{proj['id']}")
    assert resp.status_code == 401


async def test_non_member_cannot_get_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "GetPriv_NM")
    username = unique_username("getpriv_nm")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{proj['id']}")
        assert resp.status_code == 403


async def test_member_can_get_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "GetPriv_Member")
    username = unique_username("getpriv_member")
    async with member_client(username) as c:
        await admin_client.post(
            f"/api/projects/{proj['id']}/members", json={"username": username}
        )
        resp = await c.get(f"/api/projects/{proj['id']}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# strings access control
# ---------------------------------------------------------------------------

async def test_unauthenticated_can_list_strings_of_public_project(
    admin_client: AsyncClient, client: AsyncClient
):
    proj = await _create_project(admin_client, "StringsPub_Unauth", is_public=True)
    resp = await client.get(f"/api/projects/{proj['id']}/strings")
    assert resp.status_code == 200


async def test_unauthenticated_cannot_list_strings_of_private_project(
    admin_client: AsyncClient, client: AsyncClient
):
    proj = await _create_project(admin_client, "StringsPriv_Unauth")
    resp = await client.get(f"/api/projects/{proj['id']}/strings")
    assert resp.status_code == 401


async def test_non_member_cannot_list_strings_of_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "StringsPriv_NM")
    username = unique_username("str_priv_nm")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{proj['id']}/strings")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Write access: public projects allow any authenticated user to translate
# ---------------------------------------------------------------------------

async def _find_new_localization(admin_client: AsyncClient, project_id: str):
    """Return (key_id, loc_id) for the first new/empty localization in the project."""
    strings = (await admin_client.get(f"/api/projects/{project_id}/strings")).json()
    for sk in strings:
        locs = (
            await admin_client.get(f"/api/projects/{project_id}/strings/{sk['id']}/localizations")
        ).json()
        loc = next((l for l in locs if l["state"] == "new"), None)
        if loc:
            return sk["id"], loc["id"]
    return None, None


async def _find_translated_localization(admin_client: AsyncClient, project_id: str):
    """Return (key_id, loc_id) for the first translated localization in the project."""
    strings = (await admin_client.get(f"/api/projects/{project_id}/strings")).json()
    for sk in strings:
        locs = (
            await admin_client.get(f"/api/projects/{project_id}/strings/{sk['id']}/localizations")
        ).json()
        loc = next((l for l in locs if l["state"] == "translated" and l["value"]), None)
        if loc:
            return sk["id"], loc["id"]
    return None, None


async def test_authenticated_non_member_can_set_value_on_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _setup_project_with_strings(admin_client, "WritePub_NM", is_public=True)
    key_id, loc_id = await _find_new_localization(admin_client, proj["id"])
    assert loc_id is not None, "No new localization found"

    username = unique_username("write_pub_nm")
    async with member_client(username) as c:
        resp = await c.put(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Übersetzung"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "Übersetzung"


async def test_authenticated_non_member_can_create_proposal_on_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _setup_project_with_strings(admin_client, "ProposalPub_NM", is_public=True)
    key_id, loc_id = await _find_translated_localization(admin_client, proj["id"])
    assert loc_id is not None, "No translated localization found"

    username = unique_username("proposal_pub_nm")
    async with member_client(username) as c:
        resp = await c.post(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Alternativwert", "comment": "Better wording"},
        )
        assert resp.status_code == 201
        assert resp.json()["proposed_value"] == "Alternativwert"


async def test_unauthenticated_cannot_set_value_on_public_project(
    admin_client: AsyncClient, client: AsyncClient
):
    proj = await _setup_project_with_strings(admin_client, "WritePub_Unauth", is_public=True)
    key_id, loc_id = await _find_new_localization(admin_client, proj["id"])
    assert loc_id is not None

    resp = await client.put(
        f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/value",
        json={"value": "anonym"},
    )
    assert resp.status_code == 401


async def test_non_member_cannot_set_value_on_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _setup_project_with_strings(admin_client, "WritePriv_NM")
    key_id, loc_id = await _find_new_localization(admin_client, proj["id"])
    assert loc_id is not None

    username = unique_username("write_priv_nm")
    async with member_client(username) as c:
        resp = await c.put(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "verboten"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Management operations stay restricted even for public projects
# ---------------------------------------------------------------------------

async def test_non_member_cannot_update_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "UpdatePub_Restricted", is_public=True)
    username = unique_username("update_pub_nm")
    async with member_client(username) as c:
        resp = await c.patch(f"/api/projects/{proj['id']}", json={"name": "Hacked"})
        assert resp.status_code == 403


async def test_non_member_can_add_language_to_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "AddLangPub_Restricted", is_public=True)
    username = unique_username("addlang_pub_nm")
    async with member_client(username) as c:
        resp = await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "fr"})
        assert resp.status_code == 201
