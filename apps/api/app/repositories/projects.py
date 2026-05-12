from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import InternalError
from app.repositories._helpers import utc_now
from app.schemas.projects import ProjectResponse

_COLUMNS = "id, org_id, client_id, name, description, status, created_at, updated_at"


async def list_projects(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectResponse]:
    try:
        query = (
            client.from_("projects")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
        )
        if client_id is not None:
            query = query.eq("client_id", str(client_id))
        if status is not None:
            query = query.eq("status", status)
        response = await query.range(offset, offset + limit - 1).execute()
    except APIError as exc:
        raise InternalError from exc

    return [ProjectResponse.model_validate(row) for row in (response.data or [])]


async def get_project(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID,
) -> ProjectResponse | None:
    try:
        response = (
            await client.from_("projects")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .eq("id", str(project_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return ProjectResponse.model_validate(rows[0])


async def create_project(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    data: dict[str, Any],
) -> ProjectResponse:
    payload = {"org_id": str(org_id), **data}
    if "client_id" in payload:
        payload["client_id"] = str(payload["client_id"])
    try:
        response = await client.from_("projects").insert(payload).select(_COLUMNS).execute()
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError
    return ProjectResponse.model_validate(rows[0])


async def update_project(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID,
    data: dict[str, Any],
) -> ProjectResponse | None:
    try:
        response = (
            await client.from_("projects")
            .update(data)
            .eq("id", str(project_id))
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
    return ProjectResponse.model_validate(rows[0])


async def update_project_status(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID,
    status: str,
) -> ProjectResponse | None:
    try:
        response = (
            await client.from_("projects")
            .update({"status": status})
            .eq("id", str(project_id))
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
    return ProjectResponse.model_validate(rows[0])


async def soft_delete_project(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID,
) -> bool:
    try:
        response = (
            await client.from_("projects")
            .update({"deleted_at": utc_now()})
            .eq("id", str(project_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return len(rows) > 0
