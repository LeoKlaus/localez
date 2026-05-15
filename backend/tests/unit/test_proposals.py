"""
Unit tests for proposal enums and model logic — no DB required.
"""
import uuid
from datetime import UTC, datetime

from app.models.localization import Localization, LocalizationState, VariationType
from app.models.translation_proposal import ProposalStatus, TranslationProposal


def test_accepted_proposal_status():
    proposal = TranslationProposal(
        id=uuid.uuid4(),
        localization_id=uuid.uuid4(),
        proposed_value="Hallo",
        proposed_by=uuid.uuid4(),
        status=ProposalStatus.pending,
    )
    assert proposal.status == ProposalStatus.pending
    proposal.status = ProposalStatus.accepted
    assert proposal.status == ProposalStatus.accepted


def test_rejected_proposal_status():
    proposal = TranslationProposal(
        id=uuid.uuid4(),
        localization_id=uuid.uuid4(),
        proposed_value="Hallo",
        status=ProposalStatus.pending,
    )
    proposal.status = ProposalStatus.rejected
    assert proposal.status == ProposalStatus.rejected


def test_proposal_enums_are_strings():
    assert ProposalStatus.pending == "pending"
    assert ProposalStatus.accepted == "accepted"
    assert ProposalStatus.rejected == "rejected"


def test_localization_state_enums():
    assert LocalizationState.new == "new"
    assert LocalizationState.needs_review == "needs_review"
    assert LocalizationState.translated == "translated"


def test_variation_type_enums():
    assert VariationType.none == "none"
    assert VariationType.device == "device"
    assert VariationType.plural == "plural"
