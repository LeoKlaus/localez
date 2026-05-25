import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import GlobalRole, User


async def require_project_admin(
    project_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user.global_role == GlobalRole.admin:
        return user
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role == ProjectRole.admin,
        )
    )
    if member is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "Project admin role required"},
        )
    return user


async def require_reviewer(
    project_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user.global_role == GlobalRole.admin:
        return user
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role.in_([ProjectRole.admin, ProjectRole.reviewer]),
        )
    )
    if member is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "Reviewer role required"},
        )
    return user


async def require_member(
    project_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Pass for global admins and any project member (any role)."""
    if user.global_role == GlobalRole.admin:
        return user
    member = await db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "Project membership required"},
        )
    return user


# Any authenticated user can read project content
require_guest_plus = get_current_active_user
# Any project member (translator, reviewer, or admin) can write translations
require_translator_plus = require_member


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    return project
