import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.localization import Localization, LocalizationState
from app.models.translation_proposal import TranslationProposal


async def create_proposal(
    db: AsyncSession,
    localization_id: uuid.UUID,
    proposed_value: str,
    comment: str,
    proposed_by: uuid.UUID,
) -> TranslationProposal:
    loc = await db.get(Localization, localization_id)

    if loc is None or loc.value is None:
        raise ValueError("NO_VALUE")

    if loc.value == proposed_value:
        raise ValueError("DUPLICATE_PROPOSAL")

    existing = await db.scalar(
        select(TranslationProposal).where(
            TranslationProposal.localization_id == localization_id,
            TranslationProposal.proposed_by == proposed_by,
        )
    )

    if existing is not None:
        if existing.proposed_value == proposed_value:
            raise ValueError("DUPLICATE_PROPOSAL")
        existing.proposed_value = proposed_value
        existing.comment = comment
        existing.proposed_at = datetime.now(UTC)
        await db.flush()
        return existing

    proposal = TranslationProposal(
        localization_id=localization_id,
        proposed_value=proposed_value,
        comment=comment,
        proposed_by=proposed_by,
    )
    db.add(proposal)
    await db.flush()
    return proposal


async def accept_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> Localization | None:
    proposal = await db.get(TranslationProposal, proposal_id)
    if proposal is None:
        return None

    loc = await db.get(Localization, proposal.localization_id)
    if loc:
        loc.value = proposal.proposed_value
        loc.state = LocalizationState.translated

    await db.execute(
        delete(TranslationProposal).where(
            TranslationProposal.localization_id == proposal.localization_id,
        )
    )

    return loc


async def reject_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
) -> bool:
    proposal = await db.get(TranslationProposal, proposal_id)
    if proposal is None:
        return False
    await db.delete(proposal)
    return True
