import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.models.project import Project

# All authenticated users can read projects and submit translations.
require_guest_plus = get_current_active_user
require_translator_plus = get_current_active_user

# Accepting/rejecting proposals and managing projects requires admin.
require_reviewer = require_admin
require_any_language_reviewer = require_admin


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})
    return project
