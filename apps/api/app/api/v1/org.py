from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from postgrest import AsyncPostgrestClient

from app.core.deps import get_current_user, get_user_scoped_db
from app.core.tier_guard import require_org_creation_allowed
from app.repositories.org import create_org, list_orgs_for_user, update_org
from app.schemas.auth import AuthUser
from app.schemas.base import BaseResponse
from app.schemas.org import CreateOrgRequest, OrgResponse, UpdateOrgRequest

router = APIRouter(tags=["organizations"])

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
SupabaseDep = Annotated[AsyncPostgrestClient, Depends(get_user_scoped_db)]


@router.post("/organizations", dependencies=[Depends(require_org_creation_allowed)])
async def create_organization(
    body: CreateOrgRequest,
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[OrgResponse]:
    org = await create_org(
        db,
        user_id=user.user_id,
        user_email=user.email,
        name=body.name,
        slug=body.slug,
    )
    return BaseResponse(success=True, data=org)


@router.get("/organizations")
async def list_organizations(
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[list[OrgResponse]]:
    orgs = await list_orgs_for_user(db, user_id=user.user_id)
    return BaseResponse(success=True, data=orgs)


@router.patch("/organizations/{org_id}")
async def update_organization(
    org_id: UUID,
    body: UpdateOrgRequest,
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[OrgResponse]:
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    org = await update_org(
        db,
        org_id=org_id,
        user_id=user.user_id,
        fields=fields,
    )
    return BaseResponse(success=True, data=org)
