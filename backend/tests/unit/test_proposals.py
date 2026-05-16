"""
Unit tests for proposal model logic — no DB required.
"""
import uuid

from app.models.localization import Localization, LocalizationState, VariationType
from app.models.translation_proposal import TranslationProposal


def test_proposal_stores_value():
    proposal = TranslationProposal(
        id=uuid.uuid4(),
        localization_id=uuid.uuid4(),
        proposed_value="Hallo",
        proposed_by=uuid.uuid4(),
    )
    assert proposal.proposed_value == "Hallo"


def test_localization_state_enums():
    assert LocalizationState.new == "new"
    assert LocalizationState.needs_review == "needs_review"
    assert LocalizationState.translated == "translated"


def test_variation_type_enums():
    assert VariationType.none == "none"
    assert VariationType.device == "device"
    assert VariationType.plural == "plural"
