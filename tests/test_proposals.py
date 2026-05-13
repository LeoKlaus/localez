"""Integration tests for the translation proposal workflow."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def _get_user_id(admin_client, username):
    users = (await admin_client.get("/api/users?limit=200")).json()
    return next(u["id"] for u in users if u["username"] == username)


async def _add_member(admin_client, project_id, user_id, role):
    r = await admin_client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": user_id, "project_role": role},
    )
    assert r.status_code == 201


async def _first_localization(admin_client, xcstrings_project):
    """Return the first localization of 'Reviewed' key as (key_id, loc_id, loc)."""
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    # pick the German one (plain, not a variation)
    loc = next(
        (l for l in locs if l["language"] == "de" and l["variation_type"] == "none"),
        locs[0],
    )
    return key["id"], loc["id"], loc


# ---------------------------------------------------------------------------
# Create proposals
# ---------------------------------------------------------------------------

async def test_translator_can_create_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_create")
    async with member_client(username) as tr:
        user_id = await _get_user_id(admin_client, username)
        await _add_member(admin_client, pid, user_id, "translator")

        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        resp = await tr.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["proposed_value"] == "Übersetzt"
        assert data["status"] == "pending"


async def test_guest_cannot_create_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("guest_noprop")
    async with member_client(username) as guest:
        user_id = await _get_user_id(admin_client, username)
        await _add_member(admin_client, pid, user_id, "guest")

        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        resp = await guest.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )
        assert resp.status_code == 403


async def test_non_member_cannot_create_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("nomember_noprop")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List proposals
# ---------------------------------------------------------------------------

async def test_list_proposals_for_localization(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_list")
    rv_name = unique_username("rv_list")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Version 1"},
            )

            resp = await rv.get(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
            )
            assert resp.status_code == 200
            assert len(resp.json()) >= 1


async def test_list_project_proposals_dashboard(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_dash")
    rv_name = unique_username("rv_dash")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Dashboard test"},
            )

            resp = await rv.get(f"/api/projects/{pid}/proposals")
            assert resp.status_code == 200
            assert len(resp.json()) >= 1


async def test_translator_cannot_access_dashboard(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_nodash")
    async with member_client(username) as tr:
        user_id = await _get_user_id(admin_client, username)
        await _add_member(admin_client, pid, user_id, "translator")

        resp = await tr.get(f"/api/projects/{pid}/proposals")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Accept proposal
# ---------------------------------------------------------------------------

async def test_reviewer_can_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_accept")
    rv_name = unique_username("rv_accept")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            prop = (await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Akzeptiert"},
            )).json()

            resp = await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept",
                json={"reviewer_note": "Looks good"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "accepted"
            assert data["reviewer_note"] == "Looks good"


async def test_accept_updates_canonical_localization(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_canon")
    rv_name = unique_username("rv_canon")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            prop = (await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Kanonisch"},
            )).json()

            await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
            )

            loc_resp = await admin_client.get(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}"
            )
            assert loc_resp.status_code == 200
            loc = loc_resp.json()
            assert loc["value"] == "Kanonisch"
            assert loc["state"] == "translated"


async def test_accept_rejects_other_pending_proposals_atomically(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr1_name = unique_username("tr_atom1")
    tr2_name = unique_username("tr_atom2")
    rv_name = unique_username("rv_atom")

    async with member_client(tr1_name) as tr1:
        async with member_client(tr2_name) as tr2:
            async with member_client(rv_name) as rv:
                for name, role in [(tr1_name, "translator"), (tr2_name, "translator"), (rv_name, "reviewer")]:
                    uid = await _get_user_id(admin_client, name)
                    await _add_member(admin_client, pid, uid, role)

                key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
                prop1 = (await tr1.post(
                    f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                    json={"proposed_value": "Proposal One"},
                )).json()
                prop2 = (await tr2.post(
                    f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                    json={"proposed_value": "Proposal Two"},
                )).json()

                # Accept prop1 — prop2 should be automatically rejected
                await rv.post(
                    f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop1['id']}/accept"
                )

                proposals = (await rv.get(
                    f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
                )).json()
                status_by_id = {p["id"]: p["status"] for p in proposals}
                assert status_by_id[prop1["id"]] == "accepted"
                assert status_by_id[prop2["id"]] == "rejected"


async def test_translator_cannot_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_noaccept")

    async with member_client(tr_name) as tr:
        user_id = await _get_user_id(admin_client, tr_name)
        await _add_member(admin_client, pid, user_id, "translator")

        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await tr.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )).json()

        resp = await tr.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reject proposal
# ---------------------------------------------------------------------------

async def test_reviewer_can_reject_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_reject")
    rv_name = unique_username("rv_reject")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            prop = (await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Abgelehnt"},
            )).json()

            resp = await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/reject",
                json={"reviewer_note": "Not accurate"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "rejected"
            assert data["reviewer_note"] == "Not accurate"


async def test_reject_does_not_update_canonical_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_rejval")
    rv_name = unique_username("rv_rejval")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, original_loc = await _first_localization(admin_client, xcstrings_project)
            original_value = original_loc["value"]

            prop = (await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Should not be saved"},
            )).json()

            await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/reject"
            )

            loc_resp = await admin_client.get(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}"
            )
            assert loc_resp.json()["value"] == original_value


async def test_accept_already_accepted_proposal_returns_404(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr_name = unique_username("tr_dbl")
    rv_name = unique_username("rv_dbl")

    async with member_client(tr_name) as tr:
        async with member_client(rv_name) as rv:
            tr_id = await _get_user_id(admin_client, tr_name)
            rv_id = await _get_user_id(admin_client, rv_name)
            await _add_member(admin_client, pid, tr_id, "translator")
            await _add_member(admin_client, pid, rv_id, "reviewer")

            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            prop = (await tr.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Once"},
            )).json()

            await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
            )
            # Accepting again should fail — no longer pending
            resp = await rv.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
            )
            assert resp.status_code == 404
