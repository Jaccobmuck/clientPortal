from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from postgrest import AsyncPostgrestClient
from supabase import AsyncClient
from supabase_auth.errors import AuthApiError

from app.core.settings import settings
from app.db.supabase import get_supabase
from app.exceptions import UnauthorizedError
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
    # The Supabase API gateway requires `apikey` to be a valid project key;
    # the service-role key satisfies that. The user's JWT in `Authorization`
    # is what PostgREST uses for auth.uid() and RLS policy evaluation, so
    # tenancy is bound to the calling user, not the service role.
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {credentials.credentials}",
    }
    async with AsyncPostgrestClient(
        f"{settings.SUPABASE_URL}/rest/v1",
        headers=headers,
    ) as client:
        yield client
