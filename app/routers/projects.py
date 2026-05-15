import uuid

import io

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.models.localization import Localization, LocalizationState
from app.models.project import Project
from app.models.project_language import ProjectLanguage
from app.models.string_key import StringKey
from app.models.user import User
from app.schemas.project import LanguageAdd, LanguageStats, ProjectCreate, ProjectResponse, ProjectStats, ProjectUpdate
from app.schemas.string_key import LocalizationWithKeyResponse
from app.services.localization_service import fill_missing_localizations

router = APIRouter()

MAX_LIMIT = 200


async def _get_project(project_id: uuid.UUID, db: AsyncSession) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.languages))
    )
    return result.scalar_one_or_none()


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
    if body.accent_color is not None:
        project.accent_color = body.accent_color
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


@router.get("/{project_id}/icon")
async def get_icon(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None or project.icon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "ICON_NOT_FOUND", "message": "No icon set for this project"})
    return FastAPIResponse(content=project.icon, media_type="image/png")


@router.post("/{project_id}/languages", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_language(
    project_id: uuid.UUID,
    body: LanguageAdd,
    _: User = Depends(get_current_active_user),
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
    db.expire(project)
    project = await _get_project(project_id, db)
    return project


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
