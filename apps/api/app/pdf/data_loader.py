from __future__ import annotations

from typing import Any, cast

from app.pdf.viewmodel import ClientRow, InvoiceRow, LineItemRow, OrgRow

_INVOICE_COLUMNS = (
    "id, org_id, client_id, invoice_number, status, pay_token, "
    "due_date, issued_at, sent_at, paid_at, subtotal, tax_rate, tax_amount, total, notes"
)

_LINE_ITEM_COLUMNS = "id, invoice_id, description, quantity, unit_price, amount, sort_order"


async def load_invoice(
    client: Any,
    invoice_id: str,
    org_id: str,
) -> InvoiceRow | None:
    response = (
        await client.from_("invoices")
        .select(_INVOICE_COLUMNS)
        .eq("id", invoice_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return cast("InvoiceRow", rows[0])


async def load_client(
    client: Any,
    client_id: str,
    org_id: str,
) -> ClientRow | None:
    response = (
        await client.from_("clients")
        .select("id, name, email, company")
        .eq("id", client_id)
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return cast("ClientRow", rows[0])


async def load_org(
    client: Any,
    org_id: str,
) -> OrgRow | None:
    response = (
        await client.from_("organizations")
        .select("id, name, slug")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    rows = cast("list[dict[str, Any]]", response.data or [])
    if not rows:
        return None
    return cast("OrgRow", rows[0])


async def load_line_items(
    client: Any,
    invoice_id: str,
) -> list[LineItemRow]:
    response = (
        await client.from_("invoice_line_items")
        .select(_LINE_ITEM_COLUMNS)
        .eq("invoice_id", invoice_id)
        .order("sort_order")
        .execute()
    )
    return cast("list[LineItemRow]", response.data or [])


async def load_pdf_data(
    client: Any,
    invoice_id: str,
    org_id: str,
) -> tuple[InvoiceRow, ClientRow, OrgRow, list[LineItemRow]]:
    invoice = await load_invoice(client, invoice_id, org_id)
    if not invoice:
        msg = f"Invoice not found: {invoice_id} in org {org_id}"
        raise ValueError(msg)

    client_row = await load_client(client, invoice["client_id"], org_id)
    if not client_row:
        msg = f"Client not found for invoice: {invoice_id}"
        raise ValueError(msg)

    org_row = await load_org(client, org_id)
    if not org_row:
        msg = f"Organization not found: {org_id}"
        raise ValueError(msg)

    line_items = await load_line_items(client, invoice_id)

    return invoice, client_row, org_row, line_items
