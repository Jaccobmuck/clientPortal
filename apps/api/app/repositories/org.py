from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.core.permissions import OrgRole
from app.exceptions import (
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
)
from app.schemas.auth import AuthUser
from app.schemas.org import MemberResponse, OrgResponse

_ORG_COLUMNS = "id, name, slug, owner_id, created_at"

_STRIPE_CONNECT_ORG_COLUMNS = (
    "id, name, stripe_connected_account_id, stripe_connect_onboarding_complete, "
    "stripe_connect_charges_enabled, stripe_connect_payouts_enabled, "
    "stripe_connect_details_submitted"
)


@dataclass(frozen=True)
class StripeConnectOrgRecord:
    org_id: UUID
    name: str
    stripe_connect_account_id: str | None
    stripe_connect_onboarding_complete: bool
    stripe_connect_charges_enabled: bool
    stripe_connect_payouts_enabled: bool
    stripe_connect_details_submitted: bool


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


def _row_to_stripe_connect_org(row: dict[str, Any]) -> StripeConnectOrgRecord:
    return StripeConnectOrgRecord(
        org_id=UUID(str(row["id"])),
        name=str(row["name"]),
        stripe_connect_account_id=row.get("stripe_connected_account_id"),
        stripe_connect_onboarding_complete=bool(row.get("stripe_connect_onboarding_complete")),
        stripe_connect_charges_enabled=bool(row.get("stripe_connect_charges_enabled")),
        stripe_connect_payouts_enabled=bool(row.get("stripe_connect_payouts_enabled")),
        stripe_connect_details_submitted=bool(row.get("stripe_connect_details_submitted")),
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

    membership_rows = cast("list[dict[str, Any]]", membership.data or [])
    org_ids = [row["org_id"] for row in membership_rows]
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

    rows = cast("list[dict[str, Any]]", membership.data or [])
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


async def get_membership(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    user_id: UUID,
) -> OrgRole | None:
    try:
        response = (
            await client.from_("organization_members")
            .select("role")
            .eq("org_id", str(org_id))
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return OrgRole(rows[0]["role"])


async def get_stripe_connect_org(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
) -> StripeConnectOrgRecord | None:
    try:
        response = (
            await client.from_("organizations")
            .select(_STRIPE_CONNECT_ORG_COLUMNS)
            .eq("id", str(org_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return _row_to_stripe_connect_org(rows[0]) if rows else None


async def set_stripe_connect_account_id(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    account_id: str,
) -> StripeConnectOrgRecord:
    try:
        response = (
            await client.from_("organizations")
            .update({"stripe_connected_account_id": account_id})
            .eq("id", str(org_id))
            .select(_STRIPE_CONNECT_ORG_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise NotFoundError("organization not found", code="org_not_found")
    return _row_to_stripe_connect_org(rows[0])


async def get_user_by_email(
    client: AsyncPostgrestClient,
    *,
    email: str,
) -> AuthUser | None:
    try:
        response = (
            await client.from_("users").select("id, email").eq("email", email).limit(1).execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return AuthUser(user_id=UUID(rows[0]["id"]), email=rows[0].get("email"))


async def add_member(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    user_id: UUID,
    role: OrgRole,
) -> MemberResponse:
    try:
        response = (
            await client.from_("organization_members")
            .insert(
                {
                    "org_id": str(org_id),
                    "user_id": str(user_id),
                    "role": role.value,
                }
            )
            .select("user_id, role, joined_at, users(email)")
            .execute()
        )
    except APIError as exc:
        if getattr(exc, "code", None) == "23505":
            raise ConflictError(
                "user is already a member of this organization",
                code="already_member",
            ) from exc
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError
    row = rows[0]
    user_block = row.get("users") or {}
    return MemberResponse(
        user_id=UUID(row["user_id"]),
        email=user_block.get("email"),
        role=OrgRole(row["role"]),
        joined_at=row["joined_at"],
    )


async def remove_member(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    user_id: UUID,
) -> None:
    try:
        await (
            client.from_("organization_members")
            .delete()
            .eq("org_id", str(org_id))
            .eq("user_id", str(user_id))
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
