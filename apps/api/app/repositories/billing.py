from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from postgrest.exceptions import APIError

from app.exceptions import InternalError, NotFoundError

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

_BILLING_ACCOUNT_COLUMNS = (
    "id, email, stripe_customer_id, stripe_subscription_id, billing_status, "
    "billing_price_id, billing_current_period_end"
)


@dataclass(frozen=True)
class BillingAccountRecord:
    user_id: UUID
    email: str | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    billing_status: str
    billing_price_id: str | None
    billing_current_period_end: datetime | None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _row_to_billing_account(row: dict[str, Any]) -> BillingAccountRecord:
    return BillingAccountRecord(
        user_id=UUID(str(row["id"])),
        email=row.get("email"),
        stripe_customer_id=row.get("stripe_customer_id"),
        stripe_subscription_id=row.get("stripe_subscription_id"),
        billing_status=str(row.get("billing_status") or "free"),
        billing_price_id=row.get("billing_price_id"),
        billing_current_period_end=_parse_datetime(row.get("billing_current_period_end")),
    )


async def get_billing_account(
    client: AsyncPostgrestClient,
    *,
    user_id: UUID,
) -> BillingAccountRecord | None:
    try:
        response = (
            await client.from_("users")
            .select(_BILLING_ACCOUNT_COLUMNS)
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return _row_to_billing_account(rows[0]) if rows else None


async def set_stripe_customer_id(
    client: AsyncPostgrestClient,
    *,
    user_id: UUID,
    customer_id: str,
) -> BillingAccountRecord:
    try:
        response = (
            await client.from_("users")
            .update({"stripe_customer_id": customer_id})
            .eq("id", str(user_id))
            .select(_BILLING_ACCOUNT_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise NotFoundError("billing account not found", code="billing_account_not_found")
    return _row_to_billing_account(rows[0])


async def count_owned_organizations(
    client: AsyncPostgrestClient,
    *,
    user_id: UUID,
) -> int:
    try:
        response = (
            await client.from_("organizations").select("id").eq("owner_id", str(user_id)).execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return len(rows)
