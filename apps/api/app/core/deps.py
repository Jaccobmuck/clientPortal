from collections.abc import AsyncIterator
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest import AsyncPostgrestClient
from pydantic import BaseModel
from supabase import AsyncClient
from supabase_auth.errors import AuthApiError

from app.core.settings import settings
from app.db.supabase import get_supabase
from app.exceptions import ForbiddenError, UnauthorizedError
from app.schemas.auth import AuthUser

_bearer = HTTPBearer()
_depends_bearer = Depends(_bearer)


async def get_db() -> AsyncIterator[AsyncClient]:
    yield await get_supabase()


_depends_db = Depends(get_db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = _depends_bearer,
    supabase: AsyncClient = _depends_db,
) -> AuthUser:
    try:
        response = await supabase.auth.get_user(credentials.credentials)
    except AuthApiError as exc:
        raise UnauthorizedError(
            "invalid or expired token",
            code="invalid_token",
        ) from exc

    user = response.user if response is not None else None
    if user is None:
        raise UnauthorizedError(
            "invalid or expired token",
            code="invalid_token",
        )
    return AuthUser(user_id=UUID(user.id), email=user.email)


_depends_current_user = Depends(get_current_user)


async def get_user_scoped_db(
    credentials: HTTPAuthorizationCredentials = _depends_bearer,
    _user: AuthUser = _depends_current_user,
) -> AsyncIterator[AsyncPostgrestClient]:
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {credentials.credentials}",
    }
    async with AsyncPostgrestClient(
        f"{settings.SUPABASE_URL}/rest/v1",
        headers=headers,
    ) as client:
        yield client


class UserContext(BaseModel):
    user_id: UUID
    org_id: UUID


_depends_user_scoped_db = Depends(get_user_scoped_db)


_depends_header_org_id = Header()


async def get_org_context(
    x_org_id: UUID = _depends_header_org_id,
    user: AuthUser = _depends_current_user,
    db: AsyncPostgrestClient = _depends_user_scoped_db,
) -> UserContext:
    from postgrest.exceptions import APIError

    try:
        response = (
            await db.from_("organization_members")
            .select("org_id")
            .eq("org_id", str(x_org_id))
            .eq("user_id", str(user.user_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        from app.exceptions import InternalError

        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise ForbiddenError(
            "not a member of this organization",
            code="not_org_member",
        )
    return UserContext(user_id=user.user_id, org_id=x_org_id)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
SupabaseDep = Annotated[AsyncPostgrestClient, Depends(get_user_scoped_db)]
OrgUser = Annotated[UserContext, Depends(get_org_context)]
