import json
import logging
import uuid

import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse, StreamingResponse
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.config import settings
from app.core import prefill_events
from app.core.limiter import limiter
from app.database import create_db_session, get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.dependencies.project_token import generate_project_token
from app.models.localization import Localization, LocalizationState
from app.models.translation_proposal import TranslationProposal
from app.models.project import Project
from app.models.project_language import ProjectLanguage
from app.models.project_token import ProjectToken
from app.models.string_key import StringKey
from app.models.user import User
from app.schemas.project import (
    BackTranslateResponse,
    LanguageAdd, LanguageStats, PrefillResponse,
    ProjectCreate, ProjectResponse, ProjectStats, ProjectUpdate,
    ProjectTokenCreateRequest, ProjectTokenCreatedResponse, ProjectTokenResponse,
)
from app.schemas.string_key import LocalizationWithKeyResponse
from app.services.localization_service import fill_missing_localizations
from app.services import translation_service

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LIMIT = 200


async def _get_project(project_id: uuid.UUID, db: AsyncSession) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.languages))
    )
    return result.scalar_one_or_none()


async def _run_prefill(
    project_id: uuid.UUID,
    target_lang: str,
    source_lang: str,
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    raise_on_error: bool = False,
) -> tuple[int, int]:
    """Translate all state=new localizations for target_lang using the configured provider.

    Returns (filled, skipped). If raise_on_error is False (auto-prefill path), exceptions
    from the provider are logged and swallowed so language creation is unaffected.
    """
    provider = settings.prefill_provider
    if not provider:
        if raise_on_error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "PROVIDER_NOT_CONFIGURED", "message": "No prefill_provider configured"},
            )
        return 0, 0

    SourceLoc = aliased(Localization)
    rows = (await db.execute(
        select(Localization, SourceLoc.value.label("source_value"), StringKey.comment)
        .join(StringKey, StringKey.id == Localization.string_key_id)
        .outerjoin(SourceLoc, (
            (SourceLoc.string_key_id == Localization.string_key_id) &
            (SourceLoc.language == source_lang) &
            (SourceLoc.variation_type == Localization.variation_type) &
            (SourceLoc.variation_key == Localization.variation_key)
        ))
        .where(
            StringKey.project_id == project_id,
            StringKey.should_translate == True,
            Localization.language == target_lang,
            Localization.state == LocalizationState.new,
        )
    )).all()

    to_translate = [(loc, src, comment) for loc, src, comment in rows if src]
    skipped = len(rows) - len(to_translate)

    if not to_translate:
        return 0, skipped

    source_texts = [src for _, src, _ in to_translate]
    comments = [comment for _, _, comment in to_translate]
    locs = [loc for loc, _, _ in to_translate]

    try:
        translations = await translation_service.prefill(source_lang, target_lang, source_texts, provider, comments)
    except Exception as exc:
        if raise_on_error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={"code": "TRANSLATION_PROVIDER_ERROR", "message": str(exc)},
            ) from exc
        logger.error("Auto-prefill failed for project=%s lang=%s: %s", project_id, target_lang, exc)
        return 0, skipped

    for loc, value in zip(locs, translations):
        loc.ai_suggestion = value
    await db.flush()

    return len(locs), skipped


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    q = select(Project).options(selectinload(Project.languages))
    count_q = select(func.count()).select_from(Project)
    total = await db.scalar(count_q)
    result = await db.execute(q.offset(offset).limit(limit))
    projects = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = Project(name=body.name, source_language=body.source_language, created_by=user.id)
    db.add(project)
    await db.flush()
    await db.commit()
    project = await _get_project(project.id, db)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    if body.name is not None:
        project.name = body.name
    if body.source_language is not None:
        project.source_language = body.source_language
    await db.commit()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    await db.delete(project)
    await db.commit()


@router.put("/{project_id}/icon", status_code=status.HTTP_204_NO_CONTENT)
async def upload_icon(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from PIL import Image, UnidentifiedImageError
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((256, 256), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        project.icon = buf.getvalue()
    except UnidentifiedImageError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_IMAGE", "message": "File is not a valid image"})
    await db.commit()


@router.delete("/{project_id}/icon", status_code=status.HTTP_204_NO_CONTENT)
async def delete_icon(
    project_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    project.icon = None
    await db.commit()


@router.get("/{project_id}/icon")
async def get_icon(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None or project.icon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "ICON_NOT_FOUND", "message": "No icon set for this project"})
    return FastAPIResponse(content=project.icon, media_type="image/png")


async def _run_prefill_background(
    project_id: uuid.UUID, target_lang: str, source_lang: str, user_id: uuid.UUID
) -> None:
    filled, skipped = 0, 0
    try:
        async with create_db_session() as db:
            filled, skipped = await _run_prefill(project_id, target_lang, source_lang, user_id, db)
    except Exception as exc:
        logger.error("Prefill background task failed: %s", exc)
    finally:
        prefill_events.signal(project_id, target_lang, filled, skipped)


@router.post("/{project_id}/languages", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_language(
    project_id: uuid.UUID,
    body: LanguageAdd,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    if any(pl.language == body.language for pl in project.languages):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "LANGUAGE_ALREADY_EXISTS", "message": f"Language '{body.language}' is already added to this project"})

    db.add(ProjectLanguage(project_id=project_id, language=body.language))
    await db.flush()
    await fill_missing_localizations(project_id, db)
    await db.commit()
    db.expire(project, ["languages"])
    prefill_events.register(project_id, body.language)
    background_tasks.add_task(_run_prefill_background, project_id, body.language, project.source_language, user.id)
    project = await _get_project(project_id, db)
    return project


@router.post("/{project_id}/languages/{language}/prefill", response_model=PrefillResponse)
async def prefill_language(
    project_id: uuid.UUID,
    language: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectLanguage).where(
            ProjectLanguage.project_id == project_id,
            ProjectLanguage.language == language,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LANGUAGE_NOT_FOUND", "message": f"Language '{language}' not found on this project"})

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    filled, skipped = await _run_prefill(
        project_id, language, project.source_language, user.id, db, raise_on_error=True
    )
    await db.commit()
    return PrefillResponse(filled=filled, skipped=skipped)


@router.get("/{project_id}/languages/{language}/prefill/stream")
async def prefill_stream(
    project_id: uuid.UUID,
    language: str,
):
    async def generate():
        result = await prefill_events.wait_for_result(project_id, language)
        yield f"data: {result}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def _require_translation_provider() -> str:
    provider = settings.prefill_provider
    if not provider:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PROVIDER_NOT_CONFIGURED", "message": "No translation provider configured"},
        )
    return provider


async def _back_translate(source_lang: str, target_lang: str, text: str, provider: str) -> str:
    try:
        results = await translation_service.prefill(source_lang, target_lang, [text], provider)
        return results[0]
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "TRANSLATION_ERROR", "message": str(exc)},
        ) from exc


@router.post("/{project_id}/localizations/{loc_id}/back-translate", response_model=BackTranslateResponse)
async def back_translate_localization(
    project_id: uuid.UUID,
    loc_id: uuid.UUID,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    provider = _require_translation_provider()
    result = await db.execute(
        select(Localization, Project.source_language)
        .join(StringKey, Localization.string_key_id == StringKey.id)
        .join(Project, StringKey.project_id == Project.id)
        .where(Localization.id == loc_id, Project.id == project_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Localization not found"})
    loc, source_language = row
    if not loc.value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "NO_VALUE", "message": "Localization has no value to back-translate"})
    text = await _back_translate(loc.language, source_language, loc.value, provider)
    return BackTranslateResponse(text=text)


@router.post("/{project_id}/proposals/{proposal_id}/back-translate", response_model=BackTranslateResponse)
async def back_translate_proposal(
    project_id: uuid.UUID,
    proposal_id: uuid.UUID,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    provider = _require_translation_provider()
    result = await db.execute(
        select(TranslationProposal, Localization.language, Project.source_language)
        .join(Localization, TranslationProposal.localization_id == Localization.id)
        .join(StringKey, Localization.string_key_id == StringKey.id)
        .join(Project, StringKey.project_id == Project.id)
        .where(TranslationProposal.id == proposal_id, Project.id == project_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Proposal not found"})
    proposal, target_lang, source_language = row
    text = await _back_translate(target_lang, source_language, proposal.proposed_value, provider)
    return BackTranslateResponse(text=text)


@router.delete("/{project_id}/languages/{language}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_language(
    project_id: uuid.UUID,
    language: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectLanguage).where(
            ProjectLanguage.project_id == project_id,
            ProjectLanguage.language == language,
        )
    )
    pl = result.scalar_one_or_none()
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LANGUAGE_NOT_FOUND", "message": f"Language '{language}' not found on this project"})
    await db.delete(pl)
    await db.execute(
        text("""
            DELETE FROM localizations
            WHERE language = :language
            AND string_key_id IN (
                SELECT id FROM string_keys WHERE project_id = :project_id
            )
        """),
        {"language": language, "project_id": project_id},
    )
    await db.commit()


@router.get("/{project_id}/languages/{language}/localizations", response_model=list[LocalizationWithKeyResponse])
async def list_language_localizations(
    project_id: uuid.UUID,
    language: str,
    state: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    result = await db.execute(
        select(ProjectLanguage).where(
            ProjectLanguage.project_id == project_id,
            ProjectLanguage.language == language,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "LANGUAGE_NOT_FOUND", "message": f"Language '{language}' not found on this project"})

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    limit = min(limit, MAX_LIMIT)
    SourceLoc = aliased(Localization)
    query = (
        select(Localization, StringKey.key, StringKey.comment, SourceLoc.value.label("source_value"))
        .join(StringKey, StringKey.id == Localization.string_key_id)
        .outerjoin(SourceLoc, (
            (SourceLoc.string_key_id == Localization.string_key_id) &
            (SourceLoc.language == project.source_language) &
            (SourceLoc.variation_type == Localization.variation_type) &
            (SourceLoc.variation_key == Localization.variation_key)
        ))
        .where(StringKey.project_id == project_id, StringKey.should_translate == True, Localization.language == language)
    )

    if state is not None:
        try:
            query = query.where(Localization.state == LocalizationState(state))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": f"Invalid state: {state}"})

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.execute(query.offset(offset).limit(limit))

    items = []
    for loc, key, comment, source_value in rows:
        data = {c.name: getattr(loc, c.name) for c in loc.__table__.columns}
        data["key"] = key
        data["comment"] = comment
        data["source_value"] = source_value
        items.append(LocalizationWithKeyResponse.model_validate(data))

    if response:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.get("/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    total_strings = await db.scalar(
        select(func.count()).where(StringKey.project_id == project_id)
    )

    # Per (string_key, language), compute worst-case state:
    # any 'new' → missing, else any 'needs_review' → needs_review, else → translated
    rows = await db.execute(
        text("""
            SELECT
                l.language,
                SUM(CASE WHEN worst = 'new' THEN 1 ELSE 0 END)          AS missing,
                SUM(CASE WHEN worst = 'needs_review' THEN 1 ELSE 0 END) AS needs_review,
                SUM(CASE WHEN worst = 'translated' THEN 1 ELSE 0 END)   AS translated
            FROM (
                SELECT
                    l.language,
                    l.string_key_id,
                    CASE
                        WHEN bool_or(l.state = 'new')          THEN 'new'
                        WHEN bool_or(l.state = 'needs_review') THEN 'needs_review'
                        ELSE 'translated'
                    END AS worst
                FROM localizations l
                JOIN string_keys sk ON sk.id = l.string_key_id
                WHERE sk.project_id = :project_id
                GROUP BY l.language, l.string_key_id
            ) l
            GROUP BY l.language
            ORDER BY l.language
        """),
        {"project_id": project_id},
    )

    languages = [
        LanguageStats(
            language=row.language,
            translated=row.translated,
            needs_review=row.needs_review,
            missing=row.missing,
        )
        for row in rows
    ]

    return ProjectStats(total_strings=total_strings, languages=languages)


@router.post("/{project_id}/tokens", response_model=ProjectTokenCreatedResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_project_token(
    request: Request,
    project_id: uuid.UUID,
    body: ProjectTokenCreateRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    raw, token_hash = generate_project_token()
    token = ProjectToken(project_id=project_id, name=body.name, token_hash=token_hash, created_by=user.id)
    db.add(token)
    await db.flush()
    await db.refresh(token)
    await db.commit()

    return ProjectTokenCreatedResponse(
        id=token.id,
        name=token.name,
        created_by=token.created_by,
        created_at=token.created_at,
        last_used_at=None,
        token=raw,
    )


@router.get("/{project_id}/tokens", response_model=list[ProjectTokenResponse])
async def list_project_tokens(
    project_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    result = await db.execute(select(ProjectToken).where(ProjectToken.project_id == project_id))
    return result.scalars().all()


@router.delete("/{project_id}/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_project_token(
    project_id: uuid.UUID,
    token_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    token = await db.get(ProjectToken, token_id)
    if token is None or token.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "TOKEN_NOT_FOUND", "message": "Token not found"})
    await db.delete(token)
    await db.commit()
