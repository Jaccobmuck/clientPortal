from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import ConflictError, InternalError, ValidationError
from app.repositories._helpers import (
    basis_points_to_db,
    cents_to_db,
    db_to_basis_points,
    db_to_cents,
    utc_now,
)
from app.schemas.invoices import InvoiceResponse, LineItemResponse

_INVOICE_COLUMNS = (
    "id, org_id, client_id, project_id, invoice_number, status, "
    "pay_token, due_date, issued_at, sent_at, paid_at, voided_at, locked, "
    "subtotal, tax_rate, tax_amount, total, notes, created_at, updated_at"
)

_LINE_ITEM_COLUMNS = "id, invoice_id, description, quantity, unit_price, amount, sort_order"

_MAX_INVOICE_NUMBER_RETRIES = 3


def _row_to_line_item(row: dict[str, Any]) -> LineItemResponse:
    return LineItemResponse(
        id=row["id"],
        invoice_id=row["invoice_id"],
        description=row["description"],
        quantity=str(row["quantity"]),
        unit_price=db_to_cents(row["unit_price"]),
        amount=db_to_cents(row["amount"]),
        sort_order=row["sort_order"],
    )


def _row_to_response(row: dict[str, Any], line_items: list[LineItemResponse]) -> InvoiceResponse:
    return InvoiceResponse(
        id=row["id"],
        org_id=row["org_id"],
        client_id=row["client_id"],
        project_id=row.get("project_id"),
        invoice_number=row["invoice_number"],
        status=row["status"],
        pay_token=row["pay_token"],
        due_date=row.get("due_date"),
        issued_at=row.get("issued_at"),
        sent_at=row.get("sent_at"),
        paid_at=row.get("paid_at"),
        voided_at=row.get("voided_at"),
        locked=row["locked"],
        subtotal=db_to_cents(row["subtotal"]),
        tax_rate=db_to_basis_points(row["tax_rate"]),
        tax_amount=db_to_cents(row["tax_amount"]),
        total=db_to_cents(row["total"]),
        notes=row.get("notes"),
        line_items=line_items,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _compute_totals(line_items: list[dict[str, Any]], tax_rate_bp: int) -> tuple[int, int, int]:
    subtotal_cents = 0
    for item in line_items:
        qty = Decimal(str(item["quantity"]))
        price = Decimal(item["unit_price"]) / Decimal(100)
        line_amount = int(qty * price * Decimal(100))
        subtotal_cents += line_amount
    tax_amount_cents = subtotal_cents * tax_rate_bp // 10000
    total_cents = subtotal_cents + tax_amount_cents
    return subtotal_cents, tax_amount_cents, total_cents


async def _next_invoice_number(client: AsyncPostgrestClient, *, org_id: UUID) -> str:
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


async def _validate_ownership(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID,
    project_id: UUID | None,
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
        raise ValidationError(
            "client does not belong to this organization",
            code="invalid_client",
            field="client_id",
        )

    if project_id is not None:
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
            raise ValidationError(
                "project does not belong to this organization",
                code="invalid_project",
                field="project_id",
            )


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


async def list_invoices(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    client_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InvoiceResponse]:
    try:
        query = client.from_("invoices").select(_INVOICE_COLUMNS).eq("org_id", str(org_id))
        if client_id is not None:
            query = query.eq("client_id", str(client_id))
        if status is not None:
            query = query.eq("status", status)
        query = query.order("created_at", desc=True)
        response = await query.range(offset, offset + limit - 1).execute()
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    results: list[InvoiceResponse] = []
    for row in rows:
        items = await list_line_items(client, invoice_id=UUID(row["id"]))
        results.append(_row_to_response(row, items))
    return results


async def create_invoice(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    data: dict[str, Any],
) -> InvoiceResponse:
    client_id: UUID = data["client_id"]
    project_id: UUID | None = data.get("project_id")
    tax_rate_bp: int = data.get("tax_rate", 0)
    line_items_raw: list[dict[str, Any]] = data.get("line_items", [])

    await _validate_ownership(client, org_id=org_id, client_id=client_id, project_id=project_id)

    subtotal, tax_amount, total = _compute_totals(line_items_raw, tax_rate_bp)

    last_exc: APIError | None = None
    for attempt in range(_MAX_INVOICE_NUMBER_RETRIES):
        invoice_number = await _next_invoice_number(client, org_id=org_id)
        if attempt > 0:
            n = int(invoice_number.split("-", 1)[1]) + attempt
            invoice_number = f"INV-{n:04d}"

        payload: dict[str, Any] = {
            "org_id": str(org_id),
            "client_id": str(client_id),
            "invoice_number": invoice_number,
            "status": "draft",
            "subtotal": cents_to_db(subtotal),
            "tax_rate": basis_points_to_db(tax_rate_bp),
            "tax_amount": cents_to_db(tax_amount),
            "total": cents_to_db(total),
            "issued_at": utc_now(),
        }
        if project_id is not None:
            payload["project_id"] = str(project_id)
        if data.get("due_date") is not None:
            payload["due_date"] = (
                data["due_date"].isoformat()
                if hasattr(data["due_date"], "isoformat")
                else data["due_date"]
            )
        if data.get("notes") is not None:
            payload["notes"] = data["notes"]

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

    items = await _insert_line_items(client, invoice_id=invoice_id, line_items=line_items_raw)
    return _row_to_response(rows[0], items)


async def _insert_line_items(
    client: AsyncPostgrestClient,
    *,
    invoice_id: UUID,
    line_items: list[dict[str, Any]],
) -> list[LineItemResponse]:
    if not line_items:
        return []

    rows_to_insert = []
    for item in line_items:
        qty = Decimal(str(item["quantity"]))
        price_cents = item["unit_price"]
        amount_cents = int(qty * Decimal(price_cents))
        rows_to_insert.append(
            {
                "invoice_id": str(invoice_id),
                "description": item["description"],
                "quantity": str(qty),
                "unit_price": cents_to_db(price_cents),
                "amount": cents_to_db(amount_cents),
                "sort_order": item.get("sort_order", 0),
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
    if existing.locked:
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
    if data.get("notes") is not None:
        payload["notes"] = data["notes"]

    new_line_items = data.get("line_items")
    tax_rate_bp = data.get("tax_rate")

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

        rate = tax_rate_bp if tax_rate_bp is not None else existing.tax_rate
        subtotal, tax_amount, total = _compute_totals(new_line_items, rate)
        payload["subtotal"] = cents_to_db(subtotal)
        payload["tax_amount"] = cents_to_db(tax_amount)
        payload["total"] = cents_to_db(total)
        if tax_rate_bp is not None:
            payload["tax_rate"] = basis_points_to_db(tax_rate_bp)

        await _insert_line_items(client, invoice_id=invoice_id, line_items=new_line_items)
    elif tax_rate_bp is not None:
        payload["tax_rate"] = basis_points_to_db(tax_rate_bp)
        current_items = await list_line_items(client, invoice_id=invoice_id)
        raw = [{"quantity": li.quantity, "unit_price": li.unit_price} for li in current_items]
        subtotal, tax_amount, total = _compute_totals(raw, tax_rate_bp)
        payload["subtotal"] = cents_to_db(subtotal)
        payload["tax_amount"] = cents_to_db(tax_amount)
        payload["total"] = cents_to_db(total)

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
