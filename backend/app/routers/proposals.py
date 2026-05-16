import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.project_access import require_reviewer, require_translator_plus
from app.models.localization import Localization
from app.models.string_key import StringKey
from app.models.translation_proposal import TranslationProposal
from app.models.user import User
from app.schemas.proposal import ProposalCreate, ProposalResponse
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
    offset: int = 0,
    limit: int = 50,
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    key_ids = select(StringKey.id).where(StringKey.project_id == project_id)
    loc_ids = select(Localization.id).where(Localization.string_key_id.in_(key_ids))

    query = select(TranslationProposal).where(TranslationProposal.localization_id.in_(loc_ids))

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
    offset: int = 0,
    limit: int = 50,
    _: User = Depends(require_translator_plus),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    await _get_localization(db, project_id, key_id, loc_id)
    limit = min(limit, MAX_LIMIT)

    query = select(TranslationProposal).where(TranslationProposal.localization_id == loc_id)

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
    user: User = Depends(require_translator_plus),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    try:
        proposal = await proposal_service.create_proposal(db, loc_id, body.proposed_value, body.comment, user.id)
    except ValueError as e:
        if str(e) == "NO_VALUE":
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NO_VALUE", "message": "Cannot propose on a localization with no existing value"})
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "DUPLICATE_PROPOSAL", "message": "An identical proposal or translation already exists"})
    await db.commit()
    return ProposalResponse.model_validate(proposal)


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/accept", response_model=LocalizationResponse)
async def accept_proposal(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    proposal_id: uuid.UUID,
    user: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    loc = await proposal_service.accept_proposal(db, proposal_id)
    if loc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROPOSAL_NOT_FOUND", "message": "Proposal not found"})
    await db.commit()
    await db.refresh(loc)
    return loc


@router.delete("/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reject_proposal(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    proposal_id: uuid.UUID,
    _: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_localization(db, project_id, key_id, loc_id)
    found = await proposal_service.reject_proposal(db, proposal_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROPOSAL_NOT_FOUND", "message": "Proposal not found"})
    await db.commit()
