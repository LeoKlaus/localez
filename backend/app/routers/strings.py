import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.project_access import require_reviewer
from app.models.localization import Localization, LocalizationState
from app.models.project import Project
from app.models.string_key import StringKey
from app.models.translation_proposal import TranslationProposal
from app.models.user import GlobalRole, User
from app.schemas.string_key import LocalizationResponse, LocalizationStateUpdate, LocalizationValueSet, LocalizationWithKeyResponse, StringKeyDetail, StringKeyResponse
from app.services import translation_service

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


@router.put("/{project_id}/strings/{key_id}/localizations/{loc_id}/value", response_model=LocalizationResponse)
async def set_localization_value(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    body: LocalizationValueSet,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})

    if loc.value is not None and user.global_role != GlobalRole.admin and user.id != loc.value_set_by:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "VALUE_ALREADY_SET", "message": "A translation already exists; only admins or the original author can override it"})

    is_overwrite = loc.value is not None
    loc.value = body.value
    loc.value_set_by = user.id
    loc.state = LocalizationState.needs_review

    # Clear stale proposals whenever an existing value is overwritten
    if is_overwrite:
        await db.execute(
            delete(TranslationProposal).where(TranslationProposal.localization_id == loc_id)
        )

    await db.commit()
    await db.refresh(loc)
    return loc


@router.patch("/{project_id}/strings/{key_id}/localizations/{loc_id}/state", response_model=LocalizationResponse)
async def update_localization_state(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    body: LocalizationStateUpdate,
    _: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})

    loc.state = body.state

    if body.state in (LocalizationState.translated, LocalizationState.new):
        await db.execute(
            delete(TranslationProposal).where(
                TranslationProposal.localization_id == loc_id,
            )
        )

    if body.state == LocalizationState.new:
        loc.value = None
        loc.value_set_by = None

    await db.commit()
    await db.refresh(loc)
    return loc


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/reset", response_model=LocalizationResponse)
async def reset_localization(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    _: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
):
    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})

    loc.value = None
    loc.value_set_by = None
    loc.state = LocalizationState.new

    await db.execute(
        delete(TranslationProposal).where(
            TranslationProposal.localization_id == loc_id,
        )
    )

    await db.commit()
    await db.refresh(loc)
    return loc


@router.post("/{project_id}/strings/{key_id}/localizations/{loc_id}/suggest", response_model=LocalizationWithKeyResponse)
async def suggest_localization(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    loc_id: uuid.UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    provider = settings.prefill_provider
    if not provider:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PROVIDER_NOT_CONFIGURED", "message": "No translation provider configured"},
        )

    sk = await db.get(StringKey, key_id)
    if sk is None or sk.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "STRING_NOT_FOUND", "message": "String key not found"})

    loc = await db.get(Localization, loc_id)
    if loc is None or loc.string_key_id != key_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LOCALIZATION_NOT_FOUND", "message": "Localization not found"})

    if loc.state != LocalizationState.new or loc.value is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "NOT_EMPTY", "message": "Suggestions are only available for new, empty localizations"},
        )

    if loc.ai_suggestion:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "SUGGESTION_EXISTS", "message": "An AI suggestion already exists for this localization"},
        )

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    SourceLoc = aliased(Localization)
    result = await db.execute(
        select(SourceLoc).where(
            SourceLoc.string_key_id == key_id,
            SourceLoc.language == project.source_language,
            SourceLoc.variation_type == loc.variation_type,
            SourceLoc.variation_key == loc.variation_key,
        )
    )
    source_loc = result.scalar_one_or_none()

    if source_loc is None or not source_loc.value:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_SOURCE_VALUE", "message": "No source value available to translate from"},
        )

    try:
        results = await translation_service.prefill(
            project.source_language, loc.language, [source_loc.value], provider, [sk.comment]
        )
        suggestion = results[0]
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "TRANSLATION_ERROR", "message": str(exc)},
        ) from exc

    loc.ai_suggestion = suggestion
    await db.commit()
    await db.refresh(loc)

    data = {c.name: getattr(loc, c.name) for c in loc.__table__.columns}
    data["key"] = sk.key
    data["comment"] = sk.comment
    data["source_value"] = source_loc.value
    return LocalizationWithKeyResponse.model_validate(data)
