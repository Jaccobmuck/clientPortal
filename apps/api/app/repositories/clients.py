from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import InternalError, NotFoundError
from app.repositories._helpers import utc_now
from app.schemas.clients import ClientResponse

_COLUMNS = "id, org_id, name, email, phone, company, notes, created_at, updated_at"


async def list_clients(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ClientResponse]:
    try:
        query = (
            client.from_("clients")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
        )
        if search:
            query = query.or_(
                f"name.ilike.%{search}%,email.ilike.%{search}%"
            )
        response = await query.range(offset, offset + limit - 1).execute()
    except APIError as exc:
        raise InternalError from exc

    return [ClientResponse.model_validate(row) for row in (response.data or [])]


async def get_client(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
) -> ClientResponse | None:
    try:
        response = (
            await client.from_("clients")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .eq("id", str(client_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return ClientResponse.model_validate(rows[0])


async def create_client(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    data: dict[str, Any],
) -> ClientResponse:
    try:
        response = (
            await client.from_("clients")
            .insert({"org_id": str(org_id), **data})
            .select(_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError
    return ClientResponse.model_validate(rows[0])


async def update_client(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
    data: dict[str, Any],
) -> ClientResponse | None:
    try:
        response = (
            await client.from_("clients")
            .update(data)
            .eq("id", str(client_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .select(_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return ClientResponse.model_validate(rows[0])


async def soft_delete_client(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
) -> bool:
    try:
        response = (
            await client.from_("clients")
            .update({"deleted_at": utc_now()})
            .eq("id", str(client_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return len(rows) > 0
