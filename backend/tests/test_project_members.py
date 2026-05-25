"""Integration tests for per-project member management and access control."""
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_project(admin_client: AsyncClient, name: str) -> dict:
    resp = await admin_client.post("/api/projects", json={"name": name, "source_language": "en"})
    assert resp.status_code == 201
    return resp.json()


async def _add_member(admin_client: AsyncClient, project_id: str, username: str, role: str = "translator") -> dict:
    resp = await admin_client.post(
        f"/api/projects/{project_id}/members",
        json={"username": username, "role": role},
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()

# ---------------------------------------------------------------------------
# Add member
# ---------------------------------------------------------------------------

async def test_global_admin_can_add_member(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberAdd")
    username = unique_username("add_member")
    async with member_client(username):
        pass
    resp = await admin_client.post(
        f"/api/projects/{proj['id']}/members",
        json={"username": username},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == username
    assert data["role"] == "translator"
    assert data["project_id"] == proj["id"]


async def test_add_member_default_role_is_translator(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberDefaultRole")
    username = unique_username("default_role")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username)
    assert member["role"] == "translator"


async def test_add_member_with_explicit_role(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberExplicitRole")
    username = unique_username("explicit_role")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username, role="reviewer")
    assert member["role"] == "reviewer"


async def test_add_member_unknown_user_returns_404(admin_client: AsyncClient):
    proj = await _create_project(admin_client, "MemberUnknownUser")
    resp = await admin_client.post(
        f"/api/projects/{proj['id']}/members",
        json={"username": "ghost_user_xyz"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_add_member_duplicate_returns_409(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberDuplicate")
    username = unique_username("dup_member")
    async with member_client(username):
        pass
    await _add_member(admin_client, proj["id"], username)
    resp = await admin_client.post(
        f"/api/projects/{proj['id']}/members",
        json={"username": username},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "ALREADY_MEMBER"


async def test_add_member_nonexistent_project_returns_404(admin_client: AsyncClient, member_client, unique_username):
    username = unique_username("no_proj_member")
    async with member_client(username):
        pass
    resp = await admin_client.post(
        f"/api/projects/{uuid.uuid4()}/members",
        json={"username": username},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_non_member_cannot_add_member(member_client, unique_username, project: dict):
    async with member_client(unique_username("add_forbidden")) as c:
        resp = await c.post(
            f"/api/projects/{project['id']}/members",
            json={"username": "anyone"},
        )
        assert resp.status_code == 403


async def test_project_admin_member_can_add_member(
    admin_client: AsyncClient, member_client, unique_username
):
    """A user with project admin role can add other members."""
    proj = await _create_project(admin_client, "MemberAddByProjAdmin")
    proj_admin_name = unique_username("proj_admin")
    new_member_name = unique_username("new_member_via_proj_admin")

    async with member_client(proj_admin_name) as c_proj_admin:
        async with member_client(new_member_name):
            pass
        # Elevate c_proj_admin to project admin
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")

        resp = await c_proj_admin.post(
            f"/api/projects/{proj['id']}/members",
            json={"username": new_member_name},
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == new_member_name


# ---------------------------------------------------------------------------
# List members
# ---------------------------------------------------------------------------

async def test_list_members_returns_added_members(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberList")
    u1 = unique_username("list_m1")
    u2 = unique_username("list_m2")
    async with member_client(u1):
        pass
    async with member_client(u2):
        pass
    await _add_member(admin_client, proj["id"], u1, role="translator")
    await _add_member(admin_client, proj["id"], u2, role="reviewer")

    resp = await admin_client.get(f"/api/projects/{proj['id']}/members")
    assert resp.status_code == 200
    members = resp.json()
    usernames = {m["username"] for m in members}
    assert {u1, u2}.issubset(usernames)


async def test_list_members_non_member_returns_403(member_client, unique_username, project: dict):
    async with member_client(unique_username("list_forbidden")) as c:
        resp = await c.get(f"/api/projects/{project['id']}/members")
        assert resp.status_code == 403


async def test_list_members_nonexistent_project_returns_404(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/projects/{uuid.uuid4()}/members")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "PROJECT_NOT_FOUND"


async def test_project_admin_can_list_members(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberListByProjAdmin")
    proj_admin_name = unique_username("list_proj_admin")
    async with member_client(proj_admin_name) as c_proj_admin:
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")
        resp = await c_proj_admin.get(f"/api/projects/{proj['id']}/members")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Update member role
# ---------------------------------------------------------------------------

async def test_global_admin_can_update_role(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberUpdate")
    username = unique_username("update_role")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username, role="translator")

    resp = await admin_client.patch(
        f"/api/projects/{proj['id']}/members/{member['id']}",
        json={"role": "reviewer"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "reviewer"


async def test_update_role_wrong_project_returns_404(admin_client: AsyncClient, member_client, unique_username):
    proj_a = await _create_project(admin_client, "MemberUpdateWrongA")
    proj_b = await _create_project(admin_client, "MemberUpdateWrongB")
    username = unique_username("update_wrong_proj")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj_a["id"], username)

    resp = await admin_client.patch(
        f"/api/projects/{proj_b['id']}/members/{member['id']}",
        json={"role": "reviewer"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_update_nonexistent_member_returns_404(admin_client: AsyncClient, project: dict):
    resp = await admin_client.patch(
        f"/api/projects/{project['id']}/members/{uuid.uuid4()}",
        json={"role": "reviewer"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_non_member_cannot_update_role(member_client, unique_username, project: dict, admin_client: AsyncClient):
    other_name = unique_username("update_other")
    async with member_client(other_name):
        pass
    member = await _add_member(admin_client, project["id"], other_name)
    async with member_client(unique_username("update_forbidden")) as c:
        resp = await c.patch(
            f"/api/projects/{project['id']}/members/{member['id']}",
            json={"role": "admin"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Remove member
# ---------------------------------------------------------------------------

async def test_global_admin_can_remove_member(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberRemove")
    username = unique_username("remove_member")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username)

    resp = await admin_client.delete(f"/api/projects/{proj['id']}/members/{member['id']}")
    assert resp.status_code == 204

    members = (await admin_client.get(f"/api/projects/{proj['id']}/members")).json()
    assert not any(m["id"] == member["id"] for m in members)


async def test_remove_member_wrong_project_returns_404(admin_client: AsyncClient, member_client, unique_username):
    proj_a = await _create_project(admin_client, "MemberRemoveWrongA")
    proj_b = await _create_project(admin_client, "MemberRemoveWrongB")
    username = unique_username("remove_wrong_proj")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj_a["id"], username)

    resp = await admin_client.delete(f"/api/projects/{proj_b['id']}/members/{member['id']}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MEMBER_NOT_FOUND"


async def test_remove_nonexistent_member_returns_404(admin_client: AsyncClient, project: dict):
    resp = await admin_client.delete(f"/api/projects/{project['id']}/members/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_non_member_cannot_remove_member(member_client, unique_username, project: dict, admin_client: AsyncClient):
    target_name = unique_username("remove_target")
    async with member_client(target_name):
        pass
    member = await _add_member(admin_client, project["id"], target_name)
    async with member_client(unique_username("remove_forbidden")) as c:
        resp = await c.delete(f"/api/projects/{project['id']}/members/{member['id']}")
        assert resp.status_code == 403


async def test_project_admin_can_remove_member(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberRemoveByProjAdmin")
    proj_admin_name = unique_username("remove_proj_admin")
    target_name = unique_username("remove_by_proj_admin_target")
    async with member_client(proj_admin_name) as c_proj_admin:
        async with member_client(target_name):
            pass
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")
        target_member = await _add_member(admin_client, proj["id"], target_name)

        resp = await c_proj_admin.delete(f"/api/projects/{proj['id']}/members/{target_member['id']}")
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Project admin role grants access to token management
# ---------------------------------------------------------------------------

async def test_project_admin_can_create_token(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberTokenCreate")
    proj_admin_name = unique_username("token_proj_admin")
    async with member_client(proj_admin_name) as c_proj_admin:
        await _add_member(admin_client, proj["id"], proj_admin_name, role="admin")
        resp = await c_proj_admin.post(
            f"/api/projects/{proj['id']}/tokens",
            json={"name": "ci-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["token"].startswith("lz_")


async def test_project_reviewer_cannot_create_token(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberTokenReviewer")
    reviewer_name = unique_username("token_reviewer")
    async with member_client(reviewer_name) as c_reviewer:
        await _add_member(admin_client, proj["id"], reviewer_name, role="reviewer")
        resp = await c_reviewer.post(
            f"/api/projects/{proj['id']}/tokens",
            json={"name": "ci-token"},
        )
        assert resp.status_code == 403


async def test_project_translator_cannot_manage_tokens(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberTokenTranslator")
    translator_name = unique_username("token_translator")
    async with member_client(translator_name) as c_translator:
        await _add_member(admin_client, proj["id"], translator_name, role="translator")
        resp = await c_translator.get(f"/api/projects/{proj['id']}/tokens")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# add_language: any project member can add a language
# ---------------------------------------------------------------------------

async def test_translator_member_can_add_language(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "LangAddTranslator")
    translator_name = unique_username("lang_translator")
    async with member_client(translator_name) as c:
        await _add_member(admin_client, proj["id"], translator_name, role="translator")
        resp = await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "de"})
        assert resp.status_code == 201


async def test_reviewer_member_can_add_language(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "LangAddReviewer")
    reviewer_name = unique_username("lang_reviewer")
    async with member_client(reviewer_name) as c:
        await _add_member(admin_client, proj["id"], reviewer_name, role="reviewer")
        resp = await c.post(f"/api/projects/{proj['id']}/languages", json={"language": "fr"})
        assert resp.status_code == 201


async def test_non_member_cannot_add_language(member_client, unique_username, project: dict):
    async with member_client(unique_username("lang_non_member")) as c:
        resp = await c.post(f"/api/projects/{project['id']}/languages", json={"language": "ja"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cascade: members deleted when project deleted
# ---------------------------------------------------------------------------

async def test_members_deleted_when_project_deleted(admin_client: AsyncClient, member_client, unique_username):
    proj = await _create_project(admin_client, "MemberCascade")
    username = unique_username("cascade_member")
    async with member_client(username):
        pass
    member = await _add_member(admin_client, proj["id"], username)
    member_id = member["id"]

    await admin_client.delete(f"/api/projects/{proj['id']}")

    # Project is gone; any project path using that member_id should 404
    other_proj = await _create_project(admin_client, "MemberCascadeOther")
    resp = await admin_client.delete(f"/api/projects/{other_proj['id']}/members/{member_id}")
    assert resp.status_code == 404
