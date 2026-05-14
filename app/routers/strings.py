import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.project_access import require_guest_plus
from app.models.localization import Localization, LocalizationState
from app.models.user import User
from app.models.string_key import StringKey
from app.schemas.string_key import LocalizationResponse, StringKeyDetail, StringKeyResponse

router = APIRouter()

MAX_LIMIT = 200


@router.get("/{project_id}/strings", response_model=list[StringKeyResponse])
async def list_strings(
    project_id: uuid.UUID,
    language: str | None = None,
    state: LocalizationState | None = None,
    should_translate: bool | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
    _: User = Depends(require_guest_plus),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    query = select(StringKey).where(StringKey.project_id == project_id)

    if should_translate is not None:
        query = query.where(StringKey.should_translate == should_translate)
    if q:
        query = query.where(StringKey.key.ilike(f"%{q}%"))

    if language or state:
        loc_q = select(Localization.string_key_id)
        if language:
            loc_q = loc_q.where(Localization.language == language)
        if state:
            loc_q = loc_q.where(Localization.state == state)
        query = query.where(StringKey.id.in_(loc_q))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset(offset).limit(limit))
    keys = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return keys


@router.get("/{project_id}/strings/{key_id}", response_model=StringKeyDetail)
async def get_string(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    _: User = Depends(require_guest_plus),
    db: AsyncSession = Depends(get_db),
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    if not sk.should_translate:
        return StringKeyDetail(**StringKeyResponse.model_validate(sk).model_dump(), localizations=[])

    result = await db.execute(select(Localization).where(Localization.string_key_id == key_id))
    localizations = result.scalars().all()

    # Validate base fields from the ORM object first (avoids lazy-loading sk.localizations)
    base = StringKeyResponse.model_validate(sk)
    detail = StringKeyDetail(
        **base.model_dump(),
        localizations=[LocalizationResponse.model_validate(l) for l in localizations],
    )
    return detail


@router.get("/{project_id}/strings/{key_id}/localizations", response_model=list[LocalizationResponse])
async def list_localizations(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    language: str | None = None,
    state: LocalizationState | None = None,
    offset: int = 0,
    limit: int = 50,
    _: User = Depends(require_guest_plus),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    if not sk.should_translate:
        if response:
            response.headers["X-Total-Count"] = "0"
        return []

    limit = min(limit, MAX_LIMIT)
    query = select(Localization).where(Localization.string_key_id == key_id)
    if language:
        query = query.where(Localization.language == language)
    if state:
        query = query.where(Localization.state == state)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset(offset).limit(limit))
    locs = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return locs


@router.get("/{project_id}/strings/{key_id}/localizations/{loc_id}", response_model=LocalizationResponse)
async def get_localization(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    _: User = Depends(require_guest_plus),
    db: AsyncSession = Depends(get_db),
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    if not sk.should_translate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})

    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})
    return loc
