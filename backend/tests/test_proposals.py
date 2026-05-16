"""Integration tests for the translation proposal workflow."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("setup_database")


async def _first_localization(admin_client, xcstrings_project):
    """Return (key_id, loc_id, loc) for the 'Reviewed' key's German localization."""
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    key = next(s for s in strings if s["key"] == "Reviewed")
    locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
    loc = next(
        (l for l in locs if l["language"] == "de" and l["variation_type"] == "none"),
        locs[0],
    )
    return key["id"], loc["id"], loc


async def _first_new_localization(admin_client, xcstrings_project):
    """Return (key_id, loc_id) for a localization with state='new'."""
    pid = xcstrings_project["id"]
    strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
    for sk in strings:
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{sk['id']}/localizations")).json()
        for loc in locs:
            if loc["state"] == "new":
                return sk["id"], loc["id"]
    return None, None


# ---------------------------------------------------------------------------
# Create proposals
# ---------------------------------------------------------------------------

async def test_any_user_can_create_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_create")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["proposed_value"] == "Übersetzt"


async def test_unauthenticated_cannot_create_proposal(
    admin_client: AsyncClient, client: AsyncClient, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
    resp = await client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
        json={"proposed_value": "Übersetzt"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List proposals
# ---------------------------------------------------------------------------

async def test_list_proposals_for_localization(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_list")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Version 1"},
        )
        resp = await c.get(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


async def test_list_project_proposals_dashboard(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_dash")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Dashboard test"},
        )

    resp = await admin_client.get(f"/api/projects/{pid}/proposals")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_non_admin_cannot_access_dashboard(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_nodash")
    async with member_client(username) as c:
        resp = await c.get(f"/api/projects/{pid}/proposals")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Accept proposal
# ---------------------------------------------------------------------------

async def test_admin_can_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_accept")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Akzeptiert"},
        )).json()

    resp = await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["value"] == "Akzeptiert"
    assert data["state"] == "translated"


async def test_accept_updates_canonical_localization(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_canon")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Kanonisch"},
        )).json()

    await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
    )

    loc = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}"
    )).json()
    assert loc["value"] == "Kanonisch"
    assert loc["state"] == "translated"


async def test_accept_rejects_other_pending_proposals_atomically(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    tr1_name = unique_username("tr_atom1")
    tr2_name = unique_username("tr_atom2")

    async with member_client(tr1_name) as tr1:
        async with member_client(tr2_name) as tr2:
            key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
            prop1 = (await tr1.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Proposal One"},
            )).json()
            prop2 = (await tr2.post(
                f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
                json={"proposed_value": "Proposal Two"},
            )).json()

    await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop1['id']}/accept"
    )

    proposals = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
    )).json()
    proposal_ids = {p["id"] for p in proposals}
    assert prop1["id"] not in proposal_ids  # accepted proposal is also deleted
    assert prop2["id"] not in proposal_ids  # other proposals deleted on accept


async def test_non_admin_cannot_accept_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_noaccept")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Übersetzt"},
        )).json()

        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reject proposal
# ---------------------------------------------------------------------------

async def test_admin_can_reject_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_reject")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Abgelehnt"},
        )).json()

    resp = await admin_client.delete(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}"
    )
    assert resp.status_code == 204


async def test_reject_does_not_update_canonical_value(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_rejval")
    async with member_client(username) as c:
        key_id, loc_id, original_loc = await _first_localization(admin_client, xcstrings_project)
        original_value = original_loc["value"]
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Should not be saved"},
        )).json()

    await admin_client.delete(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}"
    )

    loc = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}"
    )).json()
    assert loc["value"] == original_value


# ---------------------------------------------------------------------------
# Auto-accept on new localization
# ---------------------------------------------------------------------------

async def test_proposal_on_new_localization_applies_directly(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_auto")
    async with member_client(username) as c:
        key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
        assert loc_id is not None, "No 'new' localization found in xcstrings_project"

        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Auto übersetzt"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["value"] == "Auto übersetzt"
        assert data["state"] == "needs_review"
        assert "proposed_value" not in data


async def test_auto_applied_value_not_saved_as_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_noprop")
    async with member_client(username) as c:
        key_id, loc_id = await _first_new_localization(admin_client, xcstrings_project)
        assert loc_id is not None

        await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Braucht Review"},
        )

    proposals = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
    )).json()
    assert proposals == []

    loc = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}"
    )).json()
    assert loc["state"] == "needs_review"
    assert loc["value"] == "Braucht Review"


async def test_resubmit_same_value_returns_409(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_dup")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Duplikat"},
        )
        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Duplikat"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "DUPLICATE_PROPOSAL"


async def test_resubmit_new_value_overrides_existing_proposal(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_override")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Erster Vorschlag"},
        )).json()

        resp = await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Aktualisierter Vorschlag"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == prop["id"]
        assert data["proposed_value"] == "Aktualisierter Vorschlag"

    proposals = (await admin_client.get(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals"
    )).json()
    assert len(proposals) == 1
    assert proposals[0]["proposed_value"] == "Aktualisierter Vorschlag"


async def test_proposal_matching_current_translation_returns_409(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_matchval")
    async with member_client(username) as c:
        strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
        key = next(s for s in strings if s["key"] == "Reviewed")
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
        translated_loc = next(l for l in locs if l["state"] == "translated")

        resp = await c.post(
            f"/api/projects/{pid}/strings/{key['id']}/localizations/{translated_loc['id']}/proposals",
            json={"proposed_value": translated_loc["value"]},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "DUPLICATE_PROPOSAL"


async def test_proposal_on_existing_translation_stays_pending(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_pending")
    async with member_client(username) as c:
        strings = (await admin_client.get(f"/api/projects/{pid}/strings")).json()
        key = next(s for s in strings if s["key"] == "Reviewed")
        locs = (await admin_client.get(f"/api/projects/{pid}/strings/{key['id']}/localizations")).json()
        translated_loc = next(l for l in locs if l["state"] == "translated")

        resp = await c.post(
            f"/api/projects/{pid}/strings/{key['id']}/localizations/{translated_loc['id']}/proposals",
            json={"proposed_value": "Neuer Vorschlag"},
        )
        assert resp.status_code == 201
        assert resp.json()["proposed_value"] == "Neuer Vorschlag"


async def test_accept_deleted_proposal_returns_404(
    admin_client: AsyncClient, member_client, unique_username, xcstrings_project: dict
):
    pid = xcstrings_project["id"]
    username = unique_username("tr_dbl")
    async with member_client(username) as c:
        key_id, loc_id, _ = await _first_localization(admin_client, xcstrings_project)
        prop = (await c.post(
            f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals",
            json={"proposed_value": "Once"},
        )).json()

    await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
    )
    resp = await admin_client.post(
        f"/api/projects/{pid}/strings/{key_id}/localizations/{loc_id}/proposals/{prop['id']}/accept"
    )
    assert resp.status_code == 404
