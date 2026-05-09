from typing import Any
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import (
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
)
from app.schemas.org import OrgResponse

_ORG_COLUMNS = "id, name, slug, owner_id, created_at"


def _is_slug_conflict(exc: APIError) -> bool:
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", "") or ""
    return code == "23505" or "slug_taken" in message or "duplicate key" in message


def _slug_conflict() -> ConflictError:
    return ConflictError(
        "an organization with this slug already exists",
        code="slug_taken",
        field="slug",
    )


async def create_org(
    client: AsyncPostgrestClient,
    *,
    user_id: UUID,
    user_email: str | None,
    name: str,
    slug: str,
) -> OrgResponse:
    try:
        response = await client.rpc(
            "create_organization",
            {
                "p_user_id": str(user_id),
                "p_user_email": user_email or "",
                "p_name": name,
                "p_slug": slug,
            },
        ).execute()
    except APIError as exc:
        if _is_slug_conflict(exc):
            raise _slug_conflict() from exc
        raise InternalError from exc

    data = response.data
    if not data:
        raise InternalError
    row = data[0] if isinstance(data, list) else data
    return OrgResponse.model_validate(row)


async def list_orgs_for_user(
    client: AsyncPostgrestClient,
    *,
    user_id: UUID,
) -> list[OrgResponse]:
    try:
        membership = (
            await client.from_("organization_members")
            .select("org_id")
            .eq("user_id", str(user_id))
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    org_ids = [row["org_id"] for row in (membership.data or [])]
    if not org_ids:
        return []

    try:
        orgs = await client.from_("organizations").select(_ORG_COLUMNS).in_("id", org_ids).execute()
    except APIError as exc:
        raise InternalError from exc

    return [OrgResponse.model_validate(row) for row in (orgs.data or [])]


async def update_org(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    user_id: UUID,
    fields: dict[str, Any],
) -> OrgResponse:
    try:
        membership = (
            await client.from_("organization_members")
            .select("role")
            .eq("org_id", str(org_id))
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = membership.data or []
    if not rows:
        raise NotFoundError("organization not found", code="org_not_found")
    if rows[0].get("role") != "owner":
        raise ForbiddenError(
            "only the organization owner may update this organization",
            code="not_owner",
        )

    try:
        response = (
            await client.from_("organizations")
            .update(fields)
            .eq("id", str(org_id))
            .select(_ORG_COLUMNS)
            .execute()
        )
    except APIError as exc:
        if _is_slug_conflict(exc):
            raise _slug_conflict() from exc
        raise InternalError from exc

    if not response.data:
        raise NotFoundError("organization not found", code="org_not_found")
    return OrgResponse.model_validate(response.data[0])
