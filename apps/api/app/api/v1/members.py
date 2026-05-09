from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from postgrest import AsyncPostgrestClient

from app.core.deps import get_current_user, get_user_scoped_db
from app.core.permissions import (
    assert_not_owner_removal,
    can_invite,
    can_remove_members,
    is_owner,
)
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.repositories.org import (
    add_member,
    get_membership,
    get_user_by_email,
    remove_member,
)
from app.schemas.auth import AuthUser
from app.schemas.base import BaseResponse
from app.schemas.org import InviteMemberRequest, MemberResponse

router = APIRouter(tags=["members"])

CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
SupabaseDep = Annotated[AsyncPostgrestClient, Depends(get_user_scoped_db)]


@router.post("/organizations/{org_id}/members")
async def invite_member(
    org_id: UUID,
    body: InviteMemberRequest,
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[MemberResponse]:
    caller_role = await get_membership(db, org_id=org_id, user_id=user.user_id)
    if caller_role is None:
        raise NotFoundError("organization not found", code="org_not_found")
    if not can_invite(caller_role):
        raise ForbiddenError("you do not have permission to invite members")

    invitee = await get_user_by_email(db, email=body.email)
    if invitee is None:
        raise NotFoundError("no user with that email exists", code="user_not_found")

    existing = await get_membership(db, org_id=org_id, user_id=invitee.user_id)
    if existing is not None:
        raise ConflictError(
            "user is already a member of this organization",
            code="already_member",
        )

    member = await add_member(db, org_id=org_id, user_id=invitee.user_id, role=body.role)
    return BaseResponse(success=True, data=member)


@router.delete("/organizations/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: UUID,
    user_id: UUID,
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[None]:
    caller_role = await get_membership(db, org_id=org_id, user_id=user.user_id)
    if caller_role is None:
        raise NotFoundError("organization not found", code="org_not_found")
    if not can_remove_members(caller_role):
        raise ForbiddenError("you do not have permission to remove members")

    target_role = await get_membership(db, org_id=org_id, user_id=user_id)
    if target_role is None:
        raise NotFoundError("member not found", code="member_not_found")

    assert_not_owner_removal(target_role)

    if user.user_id == user_id and is_owner(caller_role):
        raise ForbiddenError(
            "owners cannot remove themselves",
            code="cannot_self_remove",
        )

    await remove_member(db, org_id=org_id, user_id=user_id)
    return BaseResponse(success=True, data=None)
