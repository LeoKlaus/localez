import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import GlobalRole, User


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    return project


def require_project_role(*roles: ProjectRole):
    async def _check(
        project_id: uuid.UUID,
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> ProjectMember:
        # verify project exists
        project = await db.get(Project, project_id)
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

        # admins bypass membership checks
        if user.global_role == GlobalRole.admin:
            return ProjectMember(project_id=project_id, user_id=user.id, project_role=roles[0] if roles else ProjectRole.reviewer)

        result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
                ProjectMember.project_role.in_(roles),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "INSUFFICIENT_PROJECT_ROLE", "message": "Insufficient project role"},
            )
        return member

    return _check


require_guest_plus = require_project_role(ProjectRole.guest, ProjectRole.translator, ProjectRole.reviewer)
require_translator_plus = require_project_role(ProjectRole.translator, ProjectRole.reviewer)
require_reviewer = require_project_role(ProjectRole.reviewer)
