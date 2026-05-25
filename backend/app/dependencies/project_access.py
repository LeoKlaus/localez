import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user, get_optional_user
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


async def require_read_access(
    project_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Pass if: project is public (any user incl. unauthenticated), OR global admin, OR project member."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"},
        )
    if project.is_public:
        return user
    # Private project — must be authenticated
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Authentication required"},
        )
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


async def require_write_access(
    project_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Pass if: global admin, OR (public project AND authenticated), OR project member."""
    if user.global_role == GlobalRole.admin:
        return user
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"},
        )
    if project.is_public:
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


# Any authenticated user can read project content (legacy alias, now superseded by require_read_access)
require_guest_plus = get_current_active_user
# Any authenticated user with write rights: public project OR member
require_translator_plus = require_write_access


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    return project
