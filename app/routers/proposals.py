import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.project_access import require_reviewer, require_translator_plus
from app.models.localization import Localization
from app.models.project_member import ProjectMember
from app.models.string_key import StringKey
from app.models.translation_proposal import ProposalStatus, TranslationProposal
from app.schemas.proposal import ProposalCreate, ProposalResponse, ProposalReview
from app.schemas.string_key import LocalizationResponse
from app.services import proposal_service

router = APIRouter()

MAX_LIMIT = 200


async def _get_localization(db: AsyncSession, project_id: uuid.UUID, key_id: uuid.UUID, loc_id: uuid.UUID) -> Localization:
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})
    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})
    return loc


@router.get("/{project_id}/proposals", response_model=list[ProposalResponse])
async def list_project_proposals(
    project_id: uuid.UUID,
    proposal_status: ProposalStatus | None = None,
    offset: int = 0,
    limit: int = 50,
    member: ProjectMember = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    key_ids = select(StringKey.id).where(StringKey.project_id == project_id)
    loc_ids = select(Localization.id).where(Localization.string_key_id.in_(key_ids))

    query = select(TranslationProposal).where(TranslationProposal.localization_id.in_(loc_ids))
    if proposal_status:
        query = query.where(TranslationProposal.status == proposal_status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset(offset).limit(limit))
    proposals = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return proposals


@router.get("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals", response_model=list[ProposalResponse])
async def list_proposals(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    proposal_status: ProposalStatus | None = None,
    offset: int = 0,
    limit: int = 50,
    member: ProjectMember = Depends(require_translator_plus),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    await _get_localization(db, project_id, key_id, loc_id)
    limit = min(limit, MAX_LIMIT)

    query = select(TranslationProposal).where(TranslationProposal.localization_id == loc_id)
    if proposal_status:
        query = query.where(TranslationProposal.status == proposal_status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset(offset).limit(limit))
    proposals = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return proposals


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposal(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    body: ProposalCreate,
    member: ProjectMember = Depends(require_translator_plus),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    result = await proposal_service.create_proposal(db, loc_id, body.proposed_value, member.user_id)
    if isinstance(result, Localization):
        return LocalizationResponse.model_validate(result)
    return ProposalResponse.model_validate(result)


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/accept", response_model=ProposalResponse)
async def accept_proposal(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    proposal_id: uuid.UUID,
    body: ProposalReview = ProposalReview(),
    member: ProjectMember = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    proposal = await proposal_service.accept_proposal(db, proposal_id, member.user_id, body.reviewer_note)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROPOSAL_NOT_FOUND", "message": "Proposal not found or not pending"})
    return proposal


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/reject", response_model=ProposalResponse)
async def reject_proposal(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    proposal_id: uuid.UUID,
    body: ProposalReview = ProposalReview(),
    member: ProjectMember = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    proposal = await proposal_service.reject_proposal(db, proposal_id, member.user_id, body.reviewer_note)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROPOSAL_NOT_FOUND", "message": "Proposal not found or not pending"})
    return proposal
