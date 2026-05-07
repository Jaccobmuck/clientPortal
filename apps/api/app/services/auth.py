import logging

from supabase import AsyncClient
from supabase_auth.errors import AuthApiError
from supabase_auth.types import AuthResponse

from app.exceptions import ConflictError, InternalError, UnauthorizedError
from app.schemas.auth import AuthTokenData, AuthUserData

logger = logging.getLogger(__name__)


async def register_user(
    client: AsyncClient,
    *,
    email: str,
    password: str,
    full_name: str,
) -> AuthTokenData:
    try:
        response = await client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name}},
            }
        )
    except AuthApiError as exc:
        if "already registered" in exc.message.lower():
            raise ConflictError("A user with this email already exists") from exc
        logger.exception("Supabase sign-up failure")
        raise InternalError from exc

    if response.session is None:
        raise ConflictError("A user with this email already exists")

    return _build_token_data(response)


async def login_user(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> AuthTokenData:
    try:
        response = await client.auth.sign_in_with_password({"email": email, "password": password})
    except AuthApiError as exc:
        if 400 <= exc.status < 500:
            raise UnauthorizedError("Invalid credentials") from exc
        logger.exception("Supabase sign-in failure")
        raise InternalError from exc

    return _build_token_data(response)


def _build_token_data(response: AuthResponse) -> AuthTokenData:
    session = response.session
    user = response.user
    if session is None or user is None:
        raise InternalError
    return AuthTokenData(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        expires_in=session.expires_in,
        user=AuthUserData(
            id=user.id,
            email=user.email or "",
            full_name=(user.user_metadata or {}).get("full_name"),
        ),
    )
