"""
Integration tests for project-scoped permission boundaries.
"""
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")

_XCSTRINGS_PATH = Path(__file__).parent.parent / "Example.xcstrings"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Create a private project, import xcstrings, and create one proposal as admin.

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
# 1. Project visibility
# ===========================================================================

async def test_member_sees_assigned_private_project_in_list(
    admin_client: AsyncClient, member_client, unique_username
):
    """A user assigned to a private project sees it in the project list."""
    proj = await _create_project(admin_client, "Vis_AssignedPriv")
    username = unique_username("vis_assigned")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username)
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert proj["id"] in ids


async def test_member_does_not_see_unassigned_private_project_in_list(
    admin_client: AsyncClient, member_client, unique_username
):
    """A user with no membership in a private project cannot see it in the list."""
    proj = await _create_project(admin_client, "Vis_UnassignedPriv")
    username = unique_username("vis_unassigned")
    async with member_client(username) as c:
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert proj["id"] not in ids


async def test_member_sees_public_and_assigned_projects_but_not_others(
    admin_client: AsyncClient, member_client, unique_username
):
    """A user sees public projects and their own private projects, but no others."""
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


async def test_member_can_fetch_assigned_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    """Members can GET a private project they are assigned to."""
    proj = await _create_project(admin_client, "Vis_FetchAssigned")
    username = unique_username("vis_fetch_ok")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username)
        assert (await c.get(f"/api/projects/{proj['id']}")).status_code == 200


async def test_member_cannot_fetch_unassigned_private_project(
    admin_client: AsyncClient, member_client, unique_username
):
    """Authenticated users without membership cannot GET a private project."""
    proj = await _create_project(admin_client, "Vis_FetchUnassigned")
    username = unique_username("vis_fetch_no")
    async with member_client(username) as c:
        assert (await c.get(f"/api/projects/{proj['id']}")).status_code == 403


# ===========================================================================
# 2. Translator restrictions — review-level endpoints must return 403
# ===========================================================================

async def test_translator_cannot_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username
):
    proj, key_id, loc_id, proposal = await _project_with_proposal(
        admin_client, "Tr_NoAccept"
    )
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
    proj, key_id, loc_id, proposal = await _project_with_proposal(
        admin_client, "Tr_NoReject"
    )
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
        resp = await c.patch(
            f"/api/projects/{proj['id']}/strings/{key_id}/localizations/{loc_id}/state",
            json={"state": "needs_review"},
        )
        assert resp.status_code == 403


# ===========================================================================
# 3. Reviewer restrictions — admin-level endpoints must return 403
# ===========================================================================

async def test_reviewer_cannot_edit_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoEdit")
    username = unique_username("rev_no_edit")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.patch(f"/api/projects/{proj['id']}", json={"name": "Hijacked"})
        assert resp.status_code == 403


async def test_reviewer_cannot_delete_project(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoDelete")
    username = unique_username("rev_no_delete")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.delete(f"/api/projects/{proj['id']}")
        assert resp.status_code == 403


async def test_reviewer_cannot_delete_language(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoDelLang")
    await admin_client.post(
        f"/api/projects/{proj['id']}/languages", json={"language": "de"}
    )
    username = unique_username("rev_no_dellang")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.delete(f"/api/projects/{proj['id']}/languages/de")
        assert resp.status_code == 403


async def test_reviewer_cannot_import(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoImport")
    username = unique_username("rev_no_import")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.post(
            f"/api/projects/{proj['id']}/import",
            files={
                "file": (
                    _XCSTRINGS_PATH.name,
                    _XCSTRINGS_PATH.read_bytes(),
                    "application/json",
                )
            },
        )
        assert resp.status_code == 403


async def test_reviewer_cannot_export(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoExport")
    username = unique_username("rev_no_export")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.get(f"/api/projects/{proj['id']}/export")
        assert resp.status_code == 403


async def test_reviewer_cannot_create_token(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoToken")
    username = unique_username("rev_no_token")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.post(
            f"/api/projects/{proj['id']}/tokens", json={"name": "ci-token"}
        )
        assert resp.status_code == 403


async def test_reviewer_cannot_list_members(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoListMembers")
    username = unique_username("rev_no_listmembers")
    async with member_client(username) as c:
        await _add_member(admin_client, proj["id"], username, role="reviewer")
        resp = await c.get(f"/api/projects/{proj['id']}/members")
        assert resp.status_code == 403


async def test_reviewer_cannot_add_member(
    admin_client: AsyncClient, member_client, unique_username
):
    proj = await _create_project(admin_client, "Rev_NoAddMember")
    reviewer_name = unique_username("rev_no_addmember")
    target_name = unique_username("rev_addmember_target")
    async with member_client(reviewer_name) as c:
        async with member_client(target_name):
            pass  # register target user
        await _add_member(admin_client, proj["id"], reviewer_name, role="reviewer")
        resp = await c.post(
            f"/api/projects/{proj['id']}/members", json={"username": target_name}
        )
        assert resp.status_code == 403


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
        resp = await c.delete(
            f"/api/projects/{proj['id']}/members/{target_member['id']}"
        )
        assert resp.status_code == 403


# ===========================================================================
# 4. Permission scope — roles apply only to the specific project
# ===========================================================================

async def test_project_admin_in_a_cannot_edit_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Admin role in project A does not grant edit rights in project B."""
    proj_a = await _create_project(admin_client, "Scope_EditA")
    proj_b = await _create_project(admin_client, "Scope_EditB")
    username = unique_username("scope_edit_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.patch(f"/api/projects/{proj_b['id']}", json={"name": "Hijacked"})
        assert resp.status_code == 403


async def test_project_admin_in_a_cannot_delete_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Admin role in project A does not grant delete rights in project B."""
    proj_a = await _create_project(admin_client, "Scope_DeleteA")
    proj_b = await _create_project(admin_client, "Scope_DeleteB")
    username = unique_username("scope_del_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.delete(f"/api/projects/{proj_b['id']}")
        assert resp.status_code == 403


async def test_project_admin_in_a_cannot_import_into_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Admin role in project A does not grant import rights in project B."""
    proj_a = await _create_project(admin_client, "Scope_ImportA")
    proj_b = await _create_project(admin_client, "Scope_ImportB")
    username = unique_username("scope_import_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.post(
            f"/api/projects/{proj_b['id']}/import",
            files={
                "file": (
                    _XCSTRINGS_PATH.name,
                    _XCSTRINGS_PATH.read_bytes(),
                    "application/json",
                )
            },
        )
        assert resp.status_code == 403


async def test_project_admin_in_a_cannot_export_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Admin role in project A does not grant export rights in project B."""
    proj_a = await _create_project(admin_client, "Scope_ExportA")
    proj_b = await _create_project(admin_client, "Scope_ExportB")
    username = unique_username("scope_export_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.get(f"/api/projects/{proj_b['id']}/export")
        assert resp.status_code == 403


async def test_project_admin_in_a_cannot_list_members_of_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Admin role in project A does not grant access to project B's member list."""
    proj_a = await _create_project(admin_client, "Scope_MembersA")
    proj_b = await _create_project(admin_client, "Scope_MembersB")
    username = unique_username("scope_members_admin_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="admin")
        resp = await c.get(f"/api/projects/{proj_b['id']}/members")
        assert resp.status_code == 403


async def test_project_reviewer_in_a_cannot_accept_proposal_in_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Reviewer role in project A does not allow accepting proposals in project B."""
    proj_a = await _create_project(admin_client, "Scope_AcceptA")
    proj_b, key_id, loc_id, proposal = await _project_with_proposal(
        admin_client, "Scope_AcceptB"
    )
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
    """Reviewer role in project A does not allow rejecting proposals in project B."""
    proj_a = await _create_project(admin_client, "Scope_RejectA")
    proj_b, key_id, loc_id, proposal = await _project_with_proposal(
        admin_client, "Scope_RejectB"
    )
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
    """Reviewer role in project A does not allow changing localization state in project B."""
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
    proj_b = await _create_project(admin_client, "Scope_ReadB")  # private
    username = unique_username("scope_read_tr_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="translator")
        # project B should not appear in the list
        ids = [p["id"] for p in (await c.get("/api/projects")).json()]
        assert proj_b["id"] not in ids
        # direct fetch of project B should be denied
        assert (await c.get(f"/api/projects/{proj_b['id']}")).status_code == 403


async def test_project_translator_in_a_cannot_write_to_private_project_b(
    admin_client: AsyncClient, member_client, unique_username
):
    """Translator membership in project A grants no write access to private project B."""
    proj_a = await _create_project(admin_client, "Scope_WriteA")
    proj_b = await _create_project(admin_client, "Scope_WriteB")  # private
    await _import_xcstrings(admin_client, proj_b["id"])
    # The auth check fires before data lookup, so any valid (key_id, loc_id) pair works.
    key_id, loc_id = await _first_translated_loc(admin_client, proj_b["id"])
    username = unique_username("scope_write_tr_a")
    async with member_client(username) as c:
        await _add_member(admin_client, proj_a["id"], username, role="translator")
        resp = await c.put(
            f"/api/projects/{proj_b['id']}/strings/{key_id}/localizations/{loc_id}/value",
            json={"value": "Unauthorized"},
        )
        assert resp.status_code == 403
