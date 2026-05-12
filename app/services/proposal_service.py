import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.localization import Localization, LocalizationState
from app.models.translation_proposal import ProposalStatus, TranslationProposal


async def create_proposal(
    db: AsyncSession,
    localization_id: uuid.UUID,
    proposed_value: str,
    proposed_by: uuid.UUID,
) -> TranslationProposal:
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

    # reject all other pending proposals for this localization
    await db.execute(
        update(TranslationProposal)
        .where(
            TranslationProposal.localization_id == proposal.localization_id,
            TranslationProposal.id != proposal_id,
            TranslationProposal.status == ProposalStatus.pending,
        )
        .values(status=ProposalStatus.rejected, reviewed_by=reviewed_by, reviewed_at=now)
    )

    return proposal


async def reject_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    reviewed_by: uuid.UUID,
    reviewer_note: str | None = None,
) -> TranslationProposal | None:
    proposal = await db.get(TranslationProposal, proposal_id)
    if proposal is None or proposal.status != ProposalStatus.pending:
        return None

    proposal.status = ProposalStatus.rejected
    proposal.reviewed_by = reviewed_by
    proposal.reviewed_at = datetime.now(UTC)
    proposal.reviewer_note = reviewer_note
    return proposal
