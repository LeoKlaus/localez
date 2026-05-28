"""
Integration tests for project access control and permissions.
"""
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")

_XCSTRINGS_PATH = Path(__file__).parent.parent / "Example.xcstrings"


# ===========================================================================
# Helpers
# ===========================================================================

async def _create_project(
    admin_client: AsyncClient, name: str, *, is_public: bool = False
) -> dict:
    resp = await admin_client.post(
        "/api/projects",
        json={"name": name, "source_language": "en", "is_public": is_public},
    )
    assert resp.status_code == 201
    return resp.json()


async def _import_xcstrings(admin_client: AsyncClient, project_id: str) -> None:
    resp = await admin_client.post(
        f"/api/projects/{project_id}/import",
        files={"file": (_XCSTRINGS_PATH.name, _XCSTRINGS_PATH.read_bytes(), "application/json")},
    )
    assert resp.status_code == 200


async def _add_member(
    admin_client: AsyncClient, project_id: str, username: str, role: str = "translator"
) -> dict:
    resp = await admin_client.post(
        f"/api/projects/{project_id}/members",
        json={"username": username, "role": role},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


async def _first_translated_loc(
    admin_client: AsyncClient, project_id: str
) -> tuple[str, str]:
    """Return (key_id, loc_id) for the first localization with state='translated'."""
    strings = (await admin_client.get(f"/api/projects/{project_id}/strings")).json()
    for sk in strings:
        locs = (
            await admin_client.get(
                f"/api/projects/{project_id}/strings/{sk['id']}/localizations"
            )
        ).json()
        loc = next((l for l in locs if l["state"] == "translated" and l["value"]), None)
        if loc:
            return sk["id"], loc["id"]
    pytest.fail(f"No translated localization found in project {project_id}")


async def _project_with_proposal(
    admin_client: AsyncClient, name: str
) -> tuple[dict, str, str, dict]:
    """Create a private project with xcstrings imported and one proposal by admin.

    Returns (project, key_id, loc_id, proposal).
    """
    proj = await _create_project(admin_client, name)
    await _import_xcstrings(admin_client, proj["id"])
    key_id, loc_id = await _first_translated_loc(admin_client, proj["id"])
    prop_resp = await admin_client.post(
        f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/proposals",
        json={"proposed_value": "Test proposal", "comment": "for testing"},
    )
    assert prop_resp.status_code == 201, prop_resp.json()
    return proj, key_id, loc_id, prop_resp.json()


# ===========================================================================
# 1. Project list visibility
# ===========================================================================

async def test_list_projects_admin_sees_all(admin_client: AsyncClient):
    await admin_client.post("/api/projects", json={"name": "ListAll A", "source_language": "en"})
    await admin_client.post("/api/projects", json={"name": "ListAll B", "source_language": "fr"})
    resp = await admin_client.get("/api/projects")
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    names = [p["name"] for p in resp.json()]
    assert "ListAll A" in names
    assert "ListAll B" in names


async def test_list_projects_unauthenticated_returns_only_public(
    admin_client: AsyncClient, client: AsyncClient
):
    pub = await _create_project(admin_client, "ListUnauth_Pub", is_public=True)
    priv = await _create_project(admin_client, "ListUnauth_Priv")
    resp = await client.get("/api/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert pub["id"] in ids
    assert priv["id"] not in ids


async def test_member_sees_assigned_private_project_in_list(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Vis_AssignedPriv")
    username = unique_username("vis_assigned")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username)
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert proj["id"] in ids


async def test_member_sees_public_and_assigned_projects_but_not_others(
    admin_client: AsyncClient, member_client, unique_username
):
    pub = await _create_project(admin_client, "Vis_PubMixed", is_public=True)
    assigned = await _create_project(admin_client, "Vis_AssignedMixed")
    unassigned = await _create_project(admin_client, "Vis_UnassignedMixed")
    username = unique_username("vis_mixed")
    async with member_client(username) as c:
        await _add_member(admin_client, assigned["id"], username)
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert pub["id"] in ids
        assert assigned["id"] in ids
        assert unassigned["id"] not in ids


# ===========================================================================
# 2. Project get / not found
# ===========================================================================

async def test_get_project_as_admin(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "GetAdmin")
    resp = await admin_client.get(f"/api/projects/{proj['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == proj["id"]


async def test_get_project_not_found(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_member_can_fetch_assigned_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Vis_FetchAssigned")
    username = unique_username("vis_fetch_ok")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username)
        assert (await c.get(f"/api/projects/{proj['id']}")).status_code == 200


async def test_member_cannot_fetch_unassigned_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Vis_FetchUnassigned")
    username = unique_username("vis_fetch_no")
    async with member_client(username) as c:
        assert (await c.get(f"/api/projects/{proj['id']}")).status_code == 403


# ===========================================================================
# 3. Project update and delete
# ===========================================================================

async def test_update_project(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "UpdateMe")
    resp = await admin_client.patch(f"/api/projects/{proj['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


async def test_update_project_source_language(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "UpdateLang")
    resp = await admin_client.patch(f"/api/projects/{proj['id']}", json={"source_language": "fr"})
    assert resp.status_code == 200
    assert resp.json()["source_language"] == "fr"


async def test_update_project_non_member_gets_403(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "UpdateForbidden")
    username = unique_username("noupdate")
    async with member_client(username) as c:
        resp = await c.patch(f"/api/projects/{proj['id']}", json={"name": "Should fail"})
        assert resp.status_code == 403


async def test_delete_project(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "DeleteMe")
    assert (await admin_client.delete(f"/api/projects/{proj['id']}")).status_code == 204
    assert (await admin_client.get(f"/api/projects/{proj['id']}")).status_code == 404


async def test_delete_project_non_member_gets_403(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "DeleteForbidden")
    username = unique_username("nodelete")
    async with member_client(username) as c:
        assert (await c.delete(f"/api/projects/{proj['id']}")).status_code == 403


# ===========================================================================
# 4. Language management
# ===========================================================================

async def test_project_response_includes_languages(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangSchema")
    assert proj.get("languages") == []


async def test_add_and_remove_language(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangAddRemove")
    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    assert resp.status_code == 201
    assert "de" in resp.json()["languages"]

    resp = await admin_client.delete(f"/api/projects/{proj['id']}/languages/de")
    assert resp.status_code == 204
    assert "de" not in (await admin_client.get(f"/api/projects/{proj['id']}")).json()["languages"]


async def test_add_multiple_languages(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangMulti")
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "fr"})
    assert set((await admin_client.get(f"/api/projects/{proj['id']}")).json()["languages"]) == {"de", "fr"}


async def test_add_duplicate_language_returns_409(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangDup")
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LANGUAGE_ALREADY_EXISTS"


async def test_add_invalid_language_code_returns_422(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangInvalid")
    resp = await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "not-a-valid-!!-code"})
    assert resp.status_code == 422


async def test_remove_nonexistent_language_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangRemove404")
    resp = await admin_client.delete(f"/api/projects/{proj['id']}/languages/de")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


async def test_add_language_requires_auth(client: AsyncClient):
    resp = await client.post(f"/api/projects/{uuid.uuid4()}/languages", json={"language": "de"})
    assert resp.status_code == 401


async def test_translator_can_add_language(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "LangAddTranslator")
    username = unique_username("lang_translator")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="translator")
        assert (await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})).status_code == 201


async def test_reviewer_can_add_language(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "LangAddReviewer")
    username = unique_username("lang_reviewer")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "fr"})).status_code == 201


async def test_non_member_cannot_add_language_to_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "LangAddNonMember")  # private by default
    username = unique_username("lang_non_member")
    async with member_client(username) as c:
        assert (await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "ja"})).status_code == 403


async def test_authenticated_user_can_add_language_to_public_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "LangAddPublic", is_public=True)
    username = unique_username("lang_public_user")
    async with member_client(username) as c:
        resp = await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "ja"})
        assert resp.status_code == 201


# ===========================================================================
# 5. Stats
# ===========================================================================

async def test_stats_empty_project(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "StatsEmpty")
    body = (await admin_client.get(f"/api/projects/{proj['id']}/stats")).json()
    assert body["total_strings"] == 0
    assert body["languages"] == []


async def test_stats_after_import(admin_client: AsyncClient):
    """Stats are non-zero after import and each language's counts sum to total_strings."""
    proj = await _create_project(admin_client, "StatsImport")
    await _import_xcstrings(admin_client, proj["id"])
    body = (await admin_client.get(f"/api/projects/{proj['id']}/stats")).json()
    assert body["total_strings"] > 0
    assert len(body["languages"]) > 0
    for lang in body["languages"]:
        assert {"language", "translated", "needs_review", "missing"} <= lang.keys()
        assert lang["translated"] + lang["needs_review"] + lang["missing"] == body["total_strings"]


async def test_stats_not_found(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/stats")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_member_cannot_access_private_project_stats(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "StatsPrivate")
    username = unique_username("stats_user")
    async with member_client(username) as c:
        assert (await c.get(f"/api/projects/{proj['id']}/stats")).status_code == 403


# ===========================================================================
# 6. Language localizations
# ===========================================================================

async def test_language_localizations(admin_client: AsyncClient):
    """After import: list endpoint returns items, state filter works, pagination header present."""
    proj = await _create_project(admin_client, "LangLocs")
    await _import_xcstrings(admin_client, proj["id"])
    lang = (await admin_client.get(f"/api/projects/{proj['id']}")).json()["languages"][0]
    base_url = f"/api/projects/{proj['id']}/languages/{lang}/localizations"

    # Full list
    resp = await admin_client.get(base_url)
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    items = resp.json()
    assert len(items) > 0
    for item in items:
        assert item["language"] == lang
        assert "key" in item and "state" in item

    # State filter
    translated = (await admin_client.get(f"{base_url}?state=translated")).json()
    assert all(i["state"] == "translated" for i in translated)

    # Pagination
    total = int(resp.headers["X-Total-Count"])
    page = (await admin_client.get(f"{base_url}?limit=2&offset=0")).json()
    assert len(page) <= 2
    assert int((await admin_client.get(f"{base_url}?limit=2&offset=0")).headers["X-Total-Count"]) == total


async def test_language_localizations_invalid_state_returns_400(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangLocsInvalidState")
    await _import_xcstrings(admin_client, proj["id"])
    lang = (await admin_client.get(f"/api/projects/{proj['id']}")).json()["languages"][0]
    resp = await admin_client.get(f"/api/projects/{proj['id']}/languages/{lang}/localizations?state=bogus")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_STATE"


async def test_language_localizations_unknown_language_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "LangLocsUnknown")
    await _import_xcstrings(admin_client, proj["id"])
    resp = await admin_client.get(f"/api/projects/{proj['id']}/languages/zz/localizations")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LANGUAGE_NOT_FOUND"


async def test_non_member_cannot_access_private_language_localizations(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "LangLocsPrivate")
    await _import_xcstrings(admin_client, proj["id"])
    username = unique_username("loclang_user")
    async with member_client(username) as c:
        assert (await c.get(f"/api/projects/{proj['id']}/languages/en/localizations")).status_code == 403


# ===========================================================================
# 7. Member management
# ===========================================================================

async def test_global_admin_can_add_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberAdd")
    username = unique_username("add_member")
    async with member_client(username):
        pass
    resp = await admin_client.post(f"/api/projects/{proj['id']}/members", json={"username": username})
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == username
    assert data["role"] == "translator"
    assert data["project_id"] == proj["id"]


async def test_add_member_with_explicit_role(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberExplicitRole")
    username = unique_username("explicit_role")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username, role="reviewer")
    assert member["role"] == "reviewer"


async def test_add_member_unknown_user_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "MemberUnknownUser")
    resp = await admin_client.post(f"/api/projects/{proj['id']}/members", json={"username": "ghost_user_xyz"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_add_member_duplicate_returns_409(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberDuplicate")
    username = unique_username("dup_member")
    async with member_client(username):
        pass
    await _add_member(admin_client, proj["id"], username)
    resp = await admin_client.post(f"/api/projects/{proj['id']}/members", json={"username": username})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_MEMBER"


async def test_add_member_nonexistent_project_returns_404(
    admin_client: AsyncClient, member_client, unique_username
):
    username = unique_username("no_proj_member")
    async with member_client(username):
        pass
    resp = await admin_client.post(f"/api/projects/{uuid.uuid4()}/members", json={"username": username})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_member_cannot_add_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberAddForbidden")
    username = unique_username("add_forbidden")
    async with member_client(username) as c:
        resp = await c.post(f"/api/projects/{proj['id']}/members", json={"username": "anyone"})
        assert resp.status_code == 403


async def test_project_admin_can_add_and_remove_member(
    admin_client: AsyncClient, member_client, unique_username
):
    """A project admin can add and remove members within their own project."""
    proj = await _create_project(admin_client, "MemberCRUDByProjAdmin")
    proj_admin_name = unique_username("proj_admin_crud")
    target_name = unique_username("proj_admin_target")
    async with member_client(proj_admin_name) as c_proj_admin:
        async with member_client(target_name):
            pass
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")

        add_resp = await c_proj_admin.post(
            f"/api/projects/{proj['id']}/members", json={"username": target_name}
        )
        assert add_resp.status_code == 201
        target_member = add_resp.json()

        del_resp = await c_proj_admin.delete(f"/api/projects/{proj['id']}/members/{target_member['id']}")
        assert del_resp.status_code == 204


async def test_list_members_returns_added_members(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberList")
    u1, u2 = unique_username("list_m1"), unique_username("list_m2")
    for u in (u1, u2):
        async with member_client(u):
            pass
    await _add_member(admin_client, proj["id"], u1, role="translator")
    await _add_member(admin_client, proj["id"], u2, role="reviewer")
    members = (await admin_client.get(f"/api/projects/{proj['id']}/members")).json()
    assert {u1, u2}.issubset({m["username"] for m in members})


async def test_list_members_non_member_returns_403(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberListForbidden")
    username = unique_username("list_forbidden")
    async with member_client(username) as c:
        assert (await c.get(f"/api/projects/{proj['id']}/members")).status_code == 403


async def test_list_members_nonexistent_project_returns_404(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/members")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_project_admin_can_list_members(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberListByProjAdmin")
    proj_admin_name = unique_username("list_proj_admin")
    async with member_client(proj_admin_name) as c_proj_admin:
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")
        assert (await c_proj_admin.get(f"/api/projects/{proj['id']}/members")).status_code == 200


async def test_global_admin_can_update_member_role(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberUpdate")
    username = unique_username("update_role")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username, role="translator")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}/members/{member['id']}", json={"role": "reviewer"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "reviewer"


async def test_update_role_wrong_project_returns_404(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "MemberUpdateWrongA")
    proj_b = await _create_project(admin_client, "MemberUpdateWrongB")
    username = unique_username("update_wrong_proj")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj_a["id"], username)
    resp = await admin_client.patch(
        f"/api/projects/{proj_b['id']}/members/{member['id']}", json={"role": "reviewer"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_update_nonexistent_member_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "MemberUpdateNotFound")
    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}/members/{uuid.uuid4()}", json={"role": "reviewer"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_non_member_cannot_update_role(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberUpdateForbidden")
    other_name = unique_username("update_other")
    async with member_client(other_name):
        pass
    member = await _add_member(admin_client, proj["id"], other_name)
    forbidden_name = unique_username("update_forbidden")
    async with member_client(forbidden_name) as c:
        resp = await c.patch(
            f"/api/projects/{proj['id']}/members/{member['id']}", json={"role": "admin"}
        )
        assert resp.status_code == 403


async def test_global_admin_can_remove_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberRemove")
    username = unique_username("remove_member")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username)
    assert (await admin_client.delete(f"/api/projects/{proj['id']}/members/{member['id']}")).status_code == 204
    members = (await admin_client.get(f"/api/projects/{proj['id']}/members")).json()
    assert not any(m["id"] == member["id"] for m in members)


async def test_remove_member_wrong_project_returns_404(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "MemberRemoveWrongA")
    proj_b = await _create_project(admin_client, "MemberRemoveWrongB")
    username = unique_username("remove_wrong_proj")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj_a["id"], username)
    resp = await admin_client.delete(f"/api/projects/{proj_b['id']}/members/{member['id']}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_remove_nonexistent_member_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "MemberRemoveNotFound")
    assert (await admin_client.delete(f"/api/projects/{proj['id']}/members/{uuid.uuid4()}")).status_code == 404


async def test_non_member_cannot_remove_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberRemoveForbidden")
    target_name = unique_username("remove_target")
    async with member_client(target_name):
        pass
    member = await _add_member(admin_client, proj["id"], target_name)
    forbidden_name = unique_username("remove_forbidden")
    async with member_client(forbidden_name) as c:
        assert (await c.delete(f"/api/projects/{proj['id']}/members/{member['id']}")).status_code == 403


async def test_members_deleted_when_project_deleted(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "MemberCascade")
    username = unique_username("cascade_member")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username)
    await admin_client.delete(f"/api/projects/{proj['id']}")
    other_proj = await _create_project(admin_client, "MemberCascadeOther")
    assert (await admin_client.delete(f"/api/projects/{other_proj['id']}/members/{member['id']}")).status_code == 404


# ===========================================================================
# 8. Token management
# ===========================================================================

async def test_project_admin_can_create_token(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "TokenCreate")
    proj_admin_name = unique_username("token_proj_admin")
    async with member_client(proj_admin_name) as c_proj_admin:
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")
        resp = await c_proj_admin.post(f"/api/projects/{proj['id']}/tokens", json={"name": "ci-token"})
        assert resp.status_code == 201
        assert resp.json()["token"].startswith("lz_")


async def test_translator_cannot_manage_tokens(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "TokenTranslator")
    translator_name = unique_username("token_translator")
    async with member_client(translator_name) as c:
        await _add_member(admin_client, proj["id"], translator_name, role="translator")
        assert (await c.get(f"/api/projects/{proj['id']}/tokens")).status_code == 403


# ===========================================================================
# 9. Translator role: cannot use review-level endpoints
# ===========================================================================

async def test_translator_cannot_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username
):
    proj, key_id, loc_id, proposal = await _project_with_proposal(admin_client, "Tr_NoAccept")
    username = unique_username("tr_no_accept")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="translator")
        resp = await c.post(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}"
            f"/proposals/{proposal['id']}/accept"
        )
        assert resp.status_code == 403


async def test_translator_cannot_reject_proposal(
    admin_client: AsyncClient, member_client, unique_username
):
    proj, key_id, loc_id, proposal = await _project_with_proposal(admin_client, "Tr_NoReject")
    username = unique_username("tr_no_reject")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="translator")
        resp = await c.delete(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}"
            f"/proposals/{proposal['id']}"
        )
        assert resp.status_code == 403


async def test_translator_cannot_change_localization_state(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Tr_NoState")
    await _import_xcstrings(admin_client, proj["id"])
    key_id, loc_id = await _first_translated_loc(admin_client, proj["id"])
    username = unique_username("tr_no_state")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="translator")
        assert (
            await c.patch(
                f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/state",
                json={"state": "needs_review"},
            )
        ).status_code == 403


# ===========================================================================
# 10. Reviewer role: cannot use admin-level endpoints
# ===========================================================================

async def test_reviewer_cannot_edit_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoEdit")
    username = unique_username("rev_no_edit")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.patch(f"/api/projects/{proj['id']}", json={"name": "Hijacked"})).status_code == 403


async def test_reviewer_cannot_delete_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoDelete")
    username = unique_username("rev_no_delete")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.delete(f"/api/projects/{proj['id']}")).status_code == 403


async def test_reviewer_cannot_delete_language(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoDelLang")
    await admin_client.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
    username = unique_username("rev_no_dellang")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.delete(f"/api/projects/{proj['id']}/languages/de")).status_code == 403


async def test_reviewer_cannot_import(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoImport")
    username = unique_username("rev_no_import")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.post(
            f"/api/projects/{proj['id']}/import",
            files={"file": (_XCSTRINGS_PATH.name, _XCSTRINGS_PATH.read_bytes(), "application/json")},
        )
        assert resp.status_code == 403


async def test_reviewer_cannot_export(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoExport")
    username = unique_username("rev_no_export")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.get(f"/api/projects/{proj['id']}/export")).status_code == 403


async def test_reviewer_cannot_create_token(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoToken")
    username = unique_username("rev_no_token")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.post(f"/api/projects/{proj['id']}/tokens", json={"name": "ci-token"})).status_code == 403


async def test_reviewer_cannot_list_members(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoListMembers")
    username = unique_username("rev_no_listmembers")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        assert (await c.get(f"/api/projects/{proj['id']}/members")).status_code == 403


async def test_reviewer_cannot_add_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoAddMember")
    reviewer_name = unique_username("rev_no_addmember")
    target_name = unique_username("rev_addmember_target")
    async with member_client(reviewer_name) as c:
        async with member_client(target_name):
            pass
        await _add_member(admin_client, proj["id"], reviewer_name, role="reviewer")
        assert (await c.post(f"/api/projects/{proj['id']}/members", json={"username": target_name})).status_code == 403


async def test_reviewer_cannot_remove_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoRemoveMember")
    reviewer_name = unique_username("rev_no_removemember")
    target_name = unique_username("rev_removemember_target")
    async with member_client(reviewer_name) as c:
        async with member_client(target_name):
            pass
        await _add_member(admin_client, proj["id"], reviewer_name, role="reviewer")
        target_member = await _add_member(admin_client, proj["id"], target_name)
        assert (await c.delete(f"/api/projects/{proj['id']}/members/{target_member['id']}")).status_code == 403


# ===========================================================================
# 11. Cross-project isolation: role in project A grants nothing in project B
# ===========================================================================

async def test_project_admin_in_a_cannot_edit_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_EditA")
    proj_b = await _create_project(admin_client, "Scope_EditB")
    username = unique_username("scope_edit_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        assert (await c.patch(f"/api/projects/{proj_b['id']}", json={"name": "Hijacked"})).status_code == 403


async def test_project_admin_in_a_cannot_delete_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_DeleteA")
    proj_b = await _create_project(admin_client, "Scope_DeleteB")
    username = unique_username("scope_del_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        assert (await c.delete(f"/api/projects/{proj_b['id']}")).status_code == 403


async def test_project_admin_in_a_cannot_import_into_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_ImportA")
    proj_b = await _create_project(admin_client, "Scope_ImportB")
    username = unique_username("scope_import_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.post(
            f"/api/projects/{proj_b['id']}/import",
            files={"file": (_XCSTRINGS_PATH.name, _XCSTRINGS_PATH.read_bytes(), "application/json")},
        )
        assert resp.status_code == 403


async def test_project_admin_in_a_cannot_export_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_ExportA")
    proj_b = await _create_project(admin_client, "Scope_ExportB")
    username = unique_username("scope_export_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        assert (await c.get(f"/api/projects/{proj_b['id']}/export")).status_code == 403


async def test_project_admin_in_a_cannot_list_members_of_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_MembersA")
    proj_b = await _create_project(admin_client, "Scope_MembersB")
    username = unique_username("scope_members_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        assert (await c.get(f"/api/projects/{proj_b['id']}/members")).status_code == 403


async def test_project_reviewer_in_a_cannot_accept_proposal_in_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_AcceptA")
    proj_b, key_id, loc_id, proposal = await _project_with_proposal(admin_client, "Scope_AcceptB")
    username = unique_username("scope_accept_rev_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="reviewer")
        resp = await c.post(
            f"/api/projects/{proj_b['id']}/strings/{key_id}/localizations/{loc_id}"
            f"/proposals/{proposal['id']}/accept"
        )
        assert resp.status_code == 403


async def test_project_reviewer_in_a_cannot_reject_proposal_in_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_RejectA")
    proj_b, key_id, loc_id, proposal = await _project_with_proposal(admin_client, "Scope_RejectB")
    username = unique_username("scope_reject_rev_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="reviewer")
        resp = await c.delete(
            f"/api/projects/{proj_b['id']}/strings/{key_id}/localizations/{loc_id}"
            f"/proposals/{proposal['id']}"
        )
        assert resp.status_code == 403


async def test_project_reviewer_in_a_cannot_change_state_in_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    proj_a = await _create_project(admin_client, "Scope_StateA")
    proj_b = await _create_project(admin_client, "Scope_StateB")
    await _import_xcstrings(admin_client, proj_b["id"])
    key_id, loc_id = await _first_translated_loc(admin_client, proj_b["id"])
    username = unique_username("scope_state_rev_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="reviewer")
        resp = await c.patch(
            f"/api/projects/{proj_b['id']}/strings/{key_id}/localizations/{loc_id}/state",
            json={"state": "needs_review"},
        )
        assert resp.status_code == 403


async def test_project_translator_in_a_cannot_read_private_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Translator membership in project A grants no read access to private project B."""
    proj_a = await _create_project(admin_client, "Scope_ReadA")
    proj_b = await _create_project(admin_client, "Scope_ReadB")
    username = unique_username("scope_read_tr_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="translator")
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert proj_b["id"] not in ids
        assert (await c.get(f"/api/projects/{proj_b['id']}")).status_code == 403


async def test_project_translator_in_a_cannot_write_to_private_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Translator membership in project A grants no write access to private project B."""
    proj_a = await _create_project(admin_client, "Scope_WriteA")
    proj_b = await _create_project(admin_client, "Scope_WriteB")
    await _import_xcstrings(admin_client, proj_b["id"])
    key_id, loc_id = await _first_translated_loc(admin_client, proj_b["id"])
    username = unique_username("scope_write_tr_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="translator")
        resp = await c.put(
            f"/api/projects/{proj_b['id']}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Unauthorized"},
        )
        assert resp.status_code == 403
