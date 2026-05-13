import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project import MemberAdd, MemberResponse, MemberUpdate

router = APIRouter()

MAX_LIMIT = 200


@router.get("/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    limit = min(limit, MAX_LIMIT)
    total = await db.scalar(select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id))
    result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id).offset(offset).limit(limit))
    members = result.scalars().all()
    if response:
        response.headers["X-Total-Count"] = str(total)
    return members


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    body: MemberAdd,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"})

    user = await db.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "USER_NOT_FOUND", "message": "User not found"})

    existing = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == body.user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ALREADY_MEMBER", "message": "User is already a member"})

    member = ProjectMember(
        project_id=project_id,
        user_id=body.user_id,
        project_role=body.project_role,
        granted_by=admin.id,
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member


@router.patch("/{project_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found"})

    member.project_role = body.project_role
    return member


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "MEMBER_NOT_FOUND", "message": "Member not found"})
    await db.delete(member)
