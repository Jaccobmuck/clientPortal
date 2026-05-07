from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from supabase import AsyncClient

from app.core.settings import settings
from app.db.supabase import get_supabase
from app.exceptions import ForbiddenError

_bearer = HTTPBearer(auto_error=False)
_depends_bearer = Depends(_bearer)


@dataclass(frozen=True, slots=True)
class UserToken:
    user_id: str
    email: str
    role: str


async def get_db() -> AsyncIterator[AsyncClient]:
    yield await get_supabase()


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = _depends_bearer,
) -> UserToken:
    if creds is None:
        raise ForbiddenError("Missing authorization header")
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError as err:
        raise ForbiddenError("Invalid or expired token") from err
    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise ForbiddenError("Invalid token claims")
    return UserToken(
        user_id=sub,
        email=email,
        role=payload.get("role", "member"),
    )
