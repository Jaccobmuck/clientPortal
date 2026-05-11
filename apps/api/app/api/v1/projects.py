from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import OrgUser, SupabaseDep
from app.exceptions import NotFoundError
from app.repositories import projects as repo
from app.schemas.base import BaseResponse
from app.schemas.projects import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectStatus,
    UpdateProjectRequest,
    UpdateStatusRequest,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/")
async def create_project(
    body: CreateProjectRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ProjectResponse]:
    data = body.model_dump()
    project = await repo.create_project(db, org_id=ctx.org_id, data=data)
    return BaseResponse(success=True, data=project)


@router.get("/")
async def list_projects(
    ctx: OrgUser,
    db: SupabaseDep,
    client_id: UUID | None = None,
    status: ProjectStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BaseResponse[list[ProjectResponse]]:
    clamped_limit = min(limit, 100)
    projects = await repo.list_projects(
        db,
        org_id=ctx.org_id,
        client_id=client_id,
        status=status.value if status else None,
        limit=clamped_limit,
        offset=offset,
    )
    return BaseResponse(success=True, data=projects)


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ProjectResponse]:
    project = await repo.get_project(db, org_id=ctx.org_id, project_id=project_id)
    if project is None:
        raise NotFoundError("project not found", code="project_not_found")
    return BaseResponse(success=True, data=project)


@router.patch("/{project_id}")
async def update_project(
    project_id: UUID,
    body: UpdateProjectRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ProjectResponse]:
    fields = body.model_dump(exclude_unset=True)
    project = await repo.update_project(
        db,
        org_id=ctx.org_id,
        project_id=project_id,
        data=fields,
    )
    if project is None:
        raise NotFoundError("project not found", code="project_not_found")
    return BaseResponse(success=True, data=project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[None]:
    deleted = await repo.soft_delete_project(
        db, org_id=ctx.org_id, project_id=project_id
    )
    if not deleted:
        raise NotFoundError("project not found", code="project_not_found")
    return BaseResponse(success=True, data=None)


@router.patch("/{project_id}/status")
async def update_status(
    project_id: UUID,
    body: UpdateStatusRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ProjectResponse]:
    project = await repo.update_project_status(
        db,
        org_id=ctx.org_id,
        project_id=project_id,
        status=body.status.value,
    )
    if project is None:
        raise NotFoundError("project not found", code="project_not_found")
    return BaseResponse(success=True, data=project)
