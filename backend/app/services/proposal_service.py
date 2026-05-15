import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.localization import Localization, LocalizationState
from app.models.translation_proposal import ProposalStatus, TranslationProposal


async def create_proposal(
    db: AsyncSession,
    localization_id: uuid.UUID,
    proposed_value: str,
    proposed_by: uuid.UUID,
) -> TranslationProposal | Localization:
    loc = await db.get(Localization, localization_id)

    if loc is not None and loc.value == proposed_value:
        raise ValueError("DUPLICATE_PROPOSAL")

    existing = await db.scalar(
        select(TranslationProposal).where(
            TranslationProposal.localization_id == localization_id,
            TranslationProposal.proposed_value == proposed_value,
            TranslationProposal.status == ProposalStatus.pending,
        )
    )
    if existing is not None:
        raise ValueError("DUPLICATE_PROPOSAL")

    if loc is not None and loc.state == LocalizationState.new:
        loc.value = proposed_value
        loc.state = LocalizationState.needs_review
        await db.flush()
        await db.refresh(loc)
        return loc

    proposal = TranslationProposal(
        localization_id=localization_id,
        proposed_value=proposed_value,
        proposed_by=proposed_by,
    )
    db.add(proposal)
    await db.flush()
    return proposal


async def accept_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    reviewed_by: uuid.UUID,
    reviewer_note: str | None = None,
) -> TranslationProposal | None:
    proposal = await db.get(TranslationProposal, proposal_id)
    if proposal is None or proposal.status != ProposalStatus.pending:
        return None

    now = datetime.now(UTC)
    proposal.status = ProposalStatus.accepted
    proposal.reviewed_by = reviewed_by
    proposal.reviewed_at = now
    proposal.reviewer_note = reviewer_note

    # update canonical localization
    loc = await db.get(Localization, proposal.localization_id)
    if loc:
        loc.value = proposal.proposed_value
        loc.state = LocalizationState.translated

    # delete all other pending proposals for this localization
    await db.execute(
        delete(TranslationProposal).where(
            TranslationProposal.localization_id == proposal.localization_id,
            TranslationProposal.id != proposal_id,
            TranslationProposal.status == ProposalStatus.pending,
        )
    )

    return proposal


async def reject_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> bool:
    proposal = await db.get(TranslationProposal, proposal_id)
    if proposal is None or proposal.status != ProposalStatus.pending:
        return False
    await db.delete(proposal)
    return True
