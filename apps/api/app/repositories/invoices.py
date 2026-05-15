from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError
from postgrest.types import CountMethod

from app.exceptions import InternalError, NotFoundError
from app.repositories._helpers import (
    basis_points_to_db,
    cents_to_db,
    db_to_basis_points,
    db_to_cents,
)
from app.schemas.invoices import InvoiceListItem, InvoiceResponse, LineItemResponse
from app.utils.pay_tokens import generate_pay_token

_INVOICE_COLUMNS = (
    "id, org_id, client_id, project_id, invoice_number, status, "
    "pay_token, due_date, issued_at, sent_at, paid_at, voided_at, locked, "
    "subtotal, tax_rate, tax_amount, total, notes, created_at, updated_at"
)

_LINE_ITEM_COLUMNS = "id, invoice_id, description, quantity, unit_price, amount, sort_order"

_MAX_INVOICE_NUMBER_RETRIES = 3

_LIST_COLUMNS = "id, client_id, invoice_number, status, issued_at, due_date, total, created_at"

PAY_TOKEN_NULLABLE = False

_PUBLIC_INVOICE_COLUMNS = (
    "id, org_id, client_id, invoice_number, status, due_date, issued_at, "
    "sent_at, paid_at, voided_at, locked, subtotal, tax_amount, total, currency, "
    "discount_amount, pdf_storage_path"
)

_PUBLIC_ORG_COLUMNS = (
    "id, name, logo_url, brand_color, support_email, "
    "stripe_connected_account_id, stripe_payments_enabled"
)

_PUBLIC_CLIENT_COLUMNS = "id, name, email"

_PAID_PAYMENT_STATUSES = frozenset({"paid", "succeeded", "complete", "completed"})


@dataclass(frozen=True)
class PublicInvoiceLineItemRecord:
    description: str
    quantity: str
    unit_amount_cents: int
    line_total_cents: int


@dataclass(frozen=True)
class PublicInvoiceRecord:
    invoice_id: UUID
    status: str
    invoice_number: str
    issued_at: Any | None
    due_at: Any | None
    paid_at: Any | None
    voided_at: Any | None
    is_public_viewable: bool
    subtotal_cents: int
    tax_cents: int
    discount_cents: int
    total_cents: int
    amount_paid_cents: int
    amount_due_cents: int
    currency: str
    org_name: str
    org_logo_url: str | None
    org_brand_color: str | None
    org_support_email: str | None
    stripe_account_id: str | None
    stripe_payments_enabled: bool | None
    client_name: str
    client_email: str | None
    line_items: list[PublicInvoiceLineItemRecord]
    pdf_storage_path: str | None


def _row_to_line_item(row: dict[str, Any]) -> LineItemResponse:
    return LineItemResponse(
        id=row["id"],
        description=row["description"],
        quantity=str(row["quantity"]),
        unit_price_cents=db_to_cents(row["unit_price"]),
        tax_rate_bp=db_to_basis_points(row["tax_rate"]) if row.get("tax_rate") else None,
        line_total_cents=db_to_cents(row["amount"]),
    )


def _row_to_response(row: dict[str, Any], line_items: list[LineItemResponse]) -> InvoiceResponse:
    return InvoiceResponse(
        id=row["id"],
        org_id=row["org_id"],
        client_id=row["client_id"],
        project_id=row.get("project_id"),
        invoice_number=row["invoice_number"],
        status=row["status"],
        issue_date=row.get("issued_at"),
        due_date=row.get("due_date"),
        subtotal_cents=db_to_cents(row["subtotal"]),
        tax_cents=db_to_cents(row["tax_amount"]),
        total_cents=db_to_cents(row["total"]),
        memo=row.get("notes"),
        line_items=line_items,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_list_item(row: dict[str, Any]) -> InvoiceListItem:
    return InvoiceListItem(
        id=row["id"],
        client_id=row["client_id"],
        invoice_number=row["invoice_number"],
        status=row["status"],
        issue_date=row.get("issued_at"),
        due_date=row.get("due_date"),
        total_cents=db_to_cents(row["total"]),
        created_at=row["created_at"],
    )


def _row_to_public_line_item(row: dict[str, Any]) -> PublicInvoiceLineItemRecord:
    return PublicInvoiceLineItemRecord(
        description=row["description"],
        quantity=str(row["quantity"]),
        unit_amount_cents=db_to_cents(row["unit_price"]),
        line_total_cents=db_to_cents(row["amount"]),
    )


def _is_public_viewable_invoice(row: dict[str, Any]) -> bool:
    status = str(row.get("status", "")).strip().lower()
    if status == "draft":
        return False
    if status == "void":
        return bool(row.get("sent_at") or row.get("locked"))
    return status in {"sent", "locked", "paid", "disputed", "resolved"}


async def _get_public_org(
    client: AsyncPostgrestClient, *, org_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            await client.from_("organizations")
            .select(_PUBLIC_ORG_COLUMNS)
            .eq("id", str(org_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return rows[0] if rows else None


async def _get_public_client(
    client: AsyncPostgrestClient, *, client_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            await client.from_("clients")
            .select(_PUBLIC_CLIENT_COLUMNS)
            .eq("id", str(client_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return rows[0] if rows else None


async def _sum_paid_payments_cents(client: AsyncPostgrestClient, *, invoice_id: UUID) -> int:
    try:
        response = (
            await client.from_("payments")
            .select("amount, status")
            .eq("invoice_id", str(invoice_id))
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return sum(
        db_to_cents(row["amount"])
        for row in rows
        if str(row.get("status", "")).strip().lower() in _PAID_PAYMENT_STATUSES
    )


def compute_line_totals(
    line_items: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Compute invoice totals from line items with per-line tax.

    Returns (subtotal_cents, tax_cents, total_cents).
    Uses Decimal for precision with fractional quantities.
    """
    subtotal_cents = 0
    tax_cents = 0
    for item in line_items:
        qty = Decimal(str(item["quantity"]))
        price_cents = Decimal(str(item["unit_price_cents"]))
        line_subtotal = int(qty * price_cents)
        subtotal_cents += line_subtotal

        bp = item.get("tax_rate_bp")
        if bp:
            tax_cents += line_subtotal * bp // 10000

    return subtotal_cents, tax_cents, subtotal_cents + tax_cents


async def next_invoice_number(client: AsyncPostgrestClient, *, org_id: UUID) -> str:
    try:
        response = (
            await client.from_("invoices")
            .select("invoice_number")
            .eq("org_id", str(org_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return "INV-0001"

    last = rows[0]["invoice_number"]
    try:
        n = int(last.split("-", 1)[1])
    except (IndexError, ValueError):
        n = 0
    return f"INV-{n + 1:04d}"


async def validate_client_ownership(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
) -> None:
    try:
        resp = (
            await client.from_("clients")
            .select("id")
            .eq("id", str(client_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
    rows = cast("list[dict[str, Any]]", resp.data or [])
    if not rows:
        raise NotFoundError(
            "client not found in this organization",
            code="client_not_found",
        )


async def validate_project_ownership(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    project_id: UUID,
) -> None:
    try:
        resp = (
            await client.from_("projects")
            .select("id")
            .eq("id", str(project_id))
            .eq("org_id", str(org_id))
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
    rows = cast("list[dict[str, Any]]", resp.data or [])
    if not rows:
        raise NotFoundError(
            "project not found in this organization",
            code="project_not_found",
        )


async def insert_invoice(
    client: AsyncPostgrestClient,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = await client.from_("invoices").insert(payload).select(_INVOICE_COLUMNS).execute()
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError("invoice insert returned no data")
    return rows[0]


async def insert_line_items(
    client: AsyncPostgrestClient,
    *,
    invoice_id: UUID,
    line_items: list[dict[str, Any]],
) -> list[LineItemResponse]:
    if not line_items:
        return []

    rows_to_insert = []
    for idx, item in enumerate(line_items):
        qty = Decimal(str(item["quantity"]))
        price_cents = item["unit_price_cents"]
        amount_cents = int(qty * Decimal(price_cents))
        rows_to_insert.append(
            {
                "invoice_id": str(invoice_id),
                "description": item["description"],
                "quantity": str(qty),
                "unit_price": cents_to_db(price_cents),
                "amount": cents_to_db(amount_cents),
                "sort_order": idx,
            }
        )

    try:
        response = (
            await client.from_("invoice_line_items")
            .insert(rows_to_insert)
            .select(_LINE_ITEM_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return [_row_to_line_item(r) for r in rows]


async def list_line_items(
    client: AsyncPostgrestClient, *, invoice_id: UUID
) -> list[LineItemResponse]:
    try:
        response = (
            await client.from_("invoice_line_items")
            .select(_LINE_ITEM_COLUMNS)
            .eq("invoice_id", str(invoice_id))
            .order("sort_order")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
    rows = cast("list[dict[str, Any]]", response.data or [])
    return [_row_to_line_item(r) for r in rows]


async def list_public_line_items(
    client: AsyncPostgrestClient, *, invoice_id: UUID
) -> list[PublicInvoiceLineItemRecord]:
    try:
        response = (
            await client.from_("invoice_line_items")
            .select("description, quantity, unit_price, amount, sort_order")
            .eq("invoice_id", str(invoice_id))
            .order("sort_order")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
    rows = cast("list[dict[str, Any]]", response.data or [])
    return [_row_to_public_line_item(r) for r in rows]


async def get_invoice(
    client: AsyncPostgrestClient, *, org_id: UUID, invoice_id: UUID
) -> InvoiceResponse | None:
    try:
        response = (
            await client.from_("invoices")
            .select(_INVOICE_COLUMNS)
            .eq("org_id", str(org_id))
            .eq("id", str(invoice_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    items = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], items)


async def get_invoice_by_pay_token(
    client: AsyncPostgrestClient, *, pay_token: UUID
) -> InvoiceResponse | None:
    try:
        response = (
            await client.from_("invoices")
            .select(_INVOICE_COLUMNS)
            .eq("pay_token", str(pay_token))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    invoice_id = UUID(str(rows[0]["id"]))
    items = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], items)


async def get_public_invoice_by_pay_token(
    client: AsyncPostgrestClient, *, token: UUID
) -> PublicInvoiceRecord | None:
    try:
        response = (
            await client.from_("invoices")
            .select(_PUBLIC_INVOICE_COLUMNS)
            .eq("pay_token", str(token))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    invoice = rows[0]
    invoice_id = UUID(str(invoice["id"]))
    org_id = UUID(str(invoice["org_id"]))
    client_id = UUID(str(invoice["client_id"]))

    org = await _get_public_org(client, org_id=org_id)
    client_row = await _get_public_client(client, client_id=client_id)
    if org is None or client_row is None:
        raise InternalError("invoice public dependencies not found")

    line_items = await list_public_line_items(client, invoice_id=invoice_id)
    amount_paid_cents = await _sum_paid_payments_cents(client, invoice_id=invoice_id)
    total_cents = db_to_cents(invoice["total"])
    if str(invoice.get("status", "")).strip().lower() == "paid" and amount_paid_cents == 0:
        amount_paid_cents = total_cents

    return PublicInvoiceRecord(
        invoice_id=invoice_id,
        status=str(invoice["status"]),
        invoice_number=invoice["invoice_number"],
        issued_at=invoice.get("issued_at"),
        due_at=invoice.get("due_date"),
        paid_at=invoice.get("paid_at"),
        voided_at=invoice.get("voided_at"),
        is_public_viewable=_is_public_viewable_invoice(invoice),
        subtotal_cents=db_to_cents(invoice["subtotal"]),
        tax_cents=db_to_cents(invoice["tax_amount"]),
        discount_cents=db_to_cents(invoice.get("discount_amount") or 0),
        total_cents=total_cents,
        amount_paid_cents=amount_paid_cents,
        amount_due_cents=max(total_cents - amount_paid_cents, 0),
        currency=str(invoice.get("currency") or "usd").lower(),
        org_name=org["name"],
        org_logo_url=org.get("logo_url"),
        org_brand_color=org.get("brand_color"),
        org_support_email=org.get("support_email"),
        stripe_account_id=org.get("stripe_connected_account_id"),
        stripe_payments_enabled=org.get("stripe_payments_enabled"),
        client_name=client_row["name"],
        client_email=client_row.get("email"),
        line_items=line_items,
        pdf_storage_path=invoice.get("pdf_storage_path"),
    )


async def rotate_invoice_pay_token(
    client: AsyncPostgrestClient, *, org_id: UUID, invoice_id: UUID
) -> UUID | None:
    pay_token = generate_pay_token()
    try:
        response = (
            await client.from_("invoices")
            .update({"pay_token": str(pay_token)})
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .select("pay_token")
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return UUID(str(rows[0]["pay_token"]))


async def invalidate_pay_token(
    client: AsyncPostgrestClient, *, org_id: UUID, invoice_id: UUID
) -> UUID | None:
    return await rotate_invoice_pay_token(client, org_id=org_id, invoice_id=invoice_id)


async def list_invoices(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    status: str | None = None,
    issue_date_from: date | None = None,
    issue_date_to: date | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InvoiceListItem]:
    try:
        query = client.from_("invoices").select(_LIST_COLUMNS).eq("org_id", str(org_id))
        if client_id is not None:
            query = query.eq("client_id", str(client_id))
        if project_id is not None:
            query = query.eq("project_id", str(project_id))
        if status is not None:
            query = query.eq("status", status)
        if issue_date_from is not None:
            query = query.gte("issued_at", issue_date_from.isoformat())
        if issue_date_to is not None:
            query = query.lte("issued_at", issue_date_to.isoformat())
        if due_date_from is not None:
            query = query.gte("due_date", due_date_from.isoformat())
        if due_date_to is not None:
            query = query.lte("due_date", due_date_to.isoformat())
        query = query.order("created_at", desc=True)
        response = await query.range(offset, offset + limit - 1).execute()
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    return [_row_to_list_item(r) for r in rows]


async def count_invoices(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    status: str | None = None,
    issue_date_from: date | None = None,
    issue_date_to: date | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
) -> int:
    try:
        query = (
            client.from_("invoices").select("id", count=CountMethod.exact).eq("org_id", str(org_id))
        )
        if client_id is not None:
            query = query.eq("client_id", str(client_id))
        if project_id is not None:
            query = query.eq("project_id", str(project_id))
        if status is not None:
            query = query.eq("status", status)
        if issue_date_from is not None:
            query = query.gte("issued_at", issue_date_from.isoformat())
        if issue_date_to is not None:
            query = query.lte("issued_at", issue_date_to.isoformat())
        if due_date_from is not None:
            query = query.gte("due_date", due_date_from.isoformat())
        if due_date_to is not None:
            query = query.lte("due_date", due_date_to.isoformat())
        response = await query.execute()
    except APIError as exc:
        raise InternalError from exc

    return response.count or 0


# ---------------------------------------------------------------------------
# Detail & draft-update operations
# ---------------------------------------------------------------------------


async def delete_invoice_line_items(
    client: AsyncPostgrestClient,
    *,
    invoice_id: UUID,
) -> None:
    try:
        await (
            client.from_("invoice_line_items").delete().eq("invoice_id", str(invoice_id)).execute()
        )
    except APIError as exc:
        raise InternalError from exc


async def update_invoice_fields(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    payload: dict[str, Any],
) -> InvoiceResponse | None:
    if not payload:
        return await get_invoice(client, org_id=org_id, invoice_id=invoice_id)

    try:
        response = (
            await client.from_("invoices")
            .update(payload)
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .select(_INVOICE_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    items = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], items)


async def update_invoice_totals(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    subtotal_cents: int,
    tax_cents: int,
    total_cents: int,
) -> None:
    payload = {
        "subtotal": cents_to_db(subtotal_cents),
        "tax_amount": cents_to_db(tax_cents),
        "total": cents_to_db(total_cents),
    }
    try:
        await (
            client.from_("invoices")
            .update(payload)
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc


# ---------------------------------------------------------------------------
# Legacy helpers kept for existing update/send/void flows
# ---------------------------------------------------------------------------


async def _validate_ownership(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
    project_id: UUID | None,
) -> None:
    await validate_client_ownership(client, org_id=org_id, client_id=client_id)
    if project_id is not None:
        await validate_project_ownership(client, org_id=org_id, project_id=project_id)


def _compute_totals(line_items: list[dict[str, Any]], tax_rate_bp: int) -> tuple[int, int, int]:
    subtotal_cents = 0
    for item in line_items:
        qty = Decimal(str(item["quantity"]))
        price = Decimal(item.get("unit_price_cents", item.get("unit_price", 0)))
        line_amount = int(qty * price)
        subtotal_cents += line_amount
    tax_amount_cents = subtotal_cents * tax_rate_bp // 10000
    total_cents = subtotal_cents + tax_amount_cents
    return subtotal_cents, tax_amount_cents, total_cents


async def _next_invoice_number(client: AsyncPostgrestClient, *, org_id: UUID) -> str:
    return await next_invoice_number(client, org_id=org_id)


async def _insert_line_items(
    client: AsyncPostgrestClient,
    *,
    invoice_id: UUID,
    line_items: list[dict[str, Any]],
) -> list[LineItemResponse]:
    return await insert_line_items(client, invoice_id=invoice_id, line_items=line_items)


async def create_invoice(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    data: dict[str, Any],
) -> InvoiceResponse:
    client_id: UUID = data["client_id"]
    project_id: UUID | None = data.get("project_id")
    line_items_raw: list[dict[str, Any]] = data.get("line_items", [])

    await _validate_ownership(client, org_id=org_id, client_id=client_id, project_id=project_id)

    subtotal, tax_amount, total = compute_line_totals(line_items_raw)

    last_exc: APIError | None = None
    for attempt in range(_MAX_INVOICE_NUMBER_RETRIES):
        invoice_number = await next_invoice_number(client, org_id=org_id)
        if attempt > 0:
            n = int(invoice_number.split("-", 1)[1]) + attempt
            invoice_number = f"INV-{n:04d}"

        payload: dict[str, Any] = {
            "org_id": str(org_id),
            "client_id": str(client_id),
            "invoice_number": invoice_number,
            "status": "draft",
            "subtotal": cents_to_db(subtotal),
            "tax_rate": basis_points_to_db(0),
            "tax_amount": cents_to_db(tax_amount),
            "total": cents_to_db(total),
            "pay_token": str(generate_pay_token()),
        }
        if project_id is not None:
            payload["project_id"] = str(project_id)
        if data.get("issue_date") is not None:
            payload["issued_at"] = (
                data["issue_date"].isoformat()
                if hasattr(data["issue_date"], "isoformat")
                else data["issue_date"]
            )
        if data.get("due_date") is not None:
            payload["due_date"] = (
                data["due_date"].isoformat()
                if hasattr(data["due_date"], "isoformat")
                else data["due_date"]
            )
        if data.get("memo") is not None:
            payload["notes"] = data["memo"]

        try:
            response = (
                await client.from_("invoices").insert(payload).select(_INVOICE_COLUMNS).execute()
            )
            break
        except APIError as exc:
            if "23505" in str(exc) and attempt < _MAX_INVOICE_NUMBER_RETRIES - 1:
                last_exc = exc
                continue
            raise InternalError from exc
    else:
        raise InternalError("failed to generate invoice number") from last_exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        raise InternalError
    invoice_id = UUID(rows[0]["id"])

    items = await insert_line_items(client, invoice_id=invoice_id, line_items=line_items_raw)
    return _row_to_response(rows[0], items)


async def update_invoice(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    data: dict[str, Any],
) -> InvoiceResponse | None:
    existing = await get_invoice(client, org_id=org_id, invoice_id=invoice_id)
    if existing is None:
        return None
    if existing.status != "draft":
        from app.exceptions import ConflictError

        raise ConflictError("invoice is locked", code="invoice_locked")

    client_id = data.get("client_id")
    project_id = data.get("project_id")
    if client_id is not None or project_id is not None:
        await _validate_ownership(
            client,
            org_id=org_id,
            client_id=client_id or existing.client_id,
            project_id=project_id if "project_id" in data else existing.project_id,
        )

    payload: dict[str, Any] = {}
    if client_id is not None:
        payload["client_id"] = str(client_id)
    if "project_id" in data:
        payload["project_id"] = str(project_id) if project_id else None
    if data.get("due_date") is not None:
        payload["due_date"] = (
            data["due_date"].isoformat()
            if hasattr(data["due_date"], "isoformat")
            else data["due_date"]
        )
    if data.get("issue_date") is not None:
        payload["issued_at"] = (
            data["issue_date"].isoformat()
            if hasattr(data["issue_date"], "isoformat")
            else data["issue_date"]
        )
    if data.get("memo") is not None:
        payload["notes"] = data["memo"]

    new_line_items = data.get("line_items")

    if new_line_items is not None:
        try:
            await (
                client.from_("invoice_line_items")
                .delete()
                .eq("invoice_id", str(invoice_id))
                .execute()
            )
        except APIError as exc:
            raise InternalError from exc

        subtotal, tax_amount, total = compute_line_totals(new_line_items)
        payload["subtotal"] = cents_to_db(subtotal)
        payload["tax_amount"] = cents_to_db(tax_amount)
        payload["total"] = cents_to_db(total)

        await insert_line_items(client, invoice_id=invoice_id, line_items=new_line_items)

    if not payload:
        return existing

    try:
        response = (
            await client.from_("invoices")
            .update(payload)
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .select(_INVOICE_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    items_updated = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], items_updated)


async def send_invoice(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    sent_at: str,
    pay_token: UUID | None = None,
) -> InvoiceResponse | None:
    payload: dict[str, Any] = {
        "status": "sent",
        "sent_at": sent_at,
        "locked": True,
    }
    if pay_token is not None:
        payload["pay_token"] = str(pay_token)

    try:
        response = (
            await client.from_("invoices")
            .update(payload)
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .select(_INVOICE_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    send_items = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], send_items)


async def void_invoice(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    voided_at: str,
) -> InvoiceResponse | None:
    payload: dict[str, Any] = {
        "status": "void",
        "voided_at": voided_at,
    }

    try:
        response = (
            await client.from_("invoices")
            .update(payload)
            .eq("id", str(invoice_id))
            .eq("org_id", str(org_id))
            .select(_INVOICE_COLUMNS)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None

    void_items = await list_line_items(client, invoice_id=invoice_id)
    return _row_to_response(rows[0], void_items)
