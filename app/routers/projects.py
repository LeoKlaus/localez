import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.models.project import Project
from app.models.project_language import ProjectLanguage
from app.models.project_member import ProjectMember
from app.models.user import GlobalRole, User
from app.schemas.project import LanguageAdd, ProjectCreate, ProjectResponse, ProjectUpdate
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
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    limit = min(limit, MAX_LIMIT)
    if user.global_role == GlobalRole.admin:
        q = select(Project).options(selectinload(Project.languages))
        count_q = select(func.count()).select_from(Project)
    else:
        member_project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        q = select(Project).where(Project.id.in_(member_project_ids)).options(selectinload(Project.languages))
        count_q = select(func.count()).select_from(Project).where(Project.id.in_(member_project_ids))

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
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    if user.global_role != GlobalRole.admin:
        result = await db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "INSUFFICIENT_PROJECT_ROLE", "message": "Not a project member"})

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


@router.post("/{project_id}/languages", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def add_language(
    project_id: uuid.UUID,
    body: LanguageAdd,
    _: User = Depends(require_admin),
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
