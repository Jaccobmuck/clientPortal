from datetime import date
from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import InternalError
from app.repositories._helpers import cents_to_db, db_to_cents, utc_now
from app.schemas.expenses import ExpenseResponse

_COLUMNS = (
    "id, org_id, project_id, description, amount, category, "
    "receipt_url, incurred_at, created_at, updated_at"
)


def _row_to_response(row: dict[str, Any]) -> ExpenseResponse:
    return ExpenseResponse(
        id=row["id"],
        org_id=row["org_id"],
        project_id=row.get("project_id"),
        description=row["description"],
        amount=db_to_cents(row["amount"]),
        category=row.get("category"),
        receipt_url=row.get("receipt_url"),
        incurred_at=row["incurred_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_expenses(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ExpenseResponse]:
    try:
        query = (
            client.from_("expenses")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
        )
        if project_id is not None:
            query = query.eq("project_id", str(project_id))
        if date_from is not None:
            query = query.gte("incurred_at", date_from.isoformat())
        if date_to is not None:
            query = query.lte("incurred_at", date_to.isoformat())
        response = await query.range(offset, offset + limit - 1).execute()
    except APIError as exc:
        raise InternalError from exc

    return [_row_to_response(row) for row in (response.data or [])]


async def get_expense(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    expense_id: UUID,
) -> ExpenseResponse | None:
    try:
        response = (
            await client.from_("expenses")
            .select(_COLUMNS)
            .eq("org_id", str(org_id))
            .eq("id", str(expense_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return _row_to_response(rows[0])


async def create_expense(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    data: dict[str, Any],
) -> ExpenseResponse:
    payload = {"org_id": str(org_id), **data}
    if "amount" in payload:
        payload["amount"] = cents_to_db(payload["amount"])
    if "project_id" in payload and payload["project_id"] is not None:
        payload["project_id"] = str(payload["project_id"])
    if "incurred_at" in payload:
        payload["incurred_at"] = payload["incurred_at"].isoformat() if hasattr(payload["incurred_at"], "isoformat") else payload["incurred_at"]
    try:
        response = (
            await client.from_("expenses")
            .insert(payload)
            .select(_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError
    return _row_to_response(rows[0])


async def update_expense(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    expense_id: UUID,
    data: dict[str, Any],
) -> ExpenseResponse | None:
    payload = {**data}
    if "amount" in payload:
        payload["amount"] = cents_to_db(payload["amount"])
    if "project_id" in payload and payload["project_id"] is not None:
        payload["project_id"] = str(payload["project_id"])
    if "incurred_at" in payload and hasattr(payload["incurred_at"], "isoformat"):
        payload["incurred_at"] = payload["incurred_at"].isoformat()
    try:
        response = (
            await client.from_("expenses")
            .update(payload)
            .eq("id", str(expense_id))
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
    return _row_to_response(rows[0])


async def update_receipt_url(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    expense_id: UUID,
    url: str,
) -> ExpenseResponse | None:
    try:
        response = (
            await client.from_("expenses")
            .update({"receipt_url": url})
            .eq("id", str(expense_id))
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
    return _row_to_response(rows[0])


async def soft_delete_expense(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    expense_id: UUID,
) -> bool:
    try:
        response = (
            await client.from_("expenses")
            .update({"deleted_at": utc_now()})
            .eq("id", str(expense_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return len(rows) > 0
