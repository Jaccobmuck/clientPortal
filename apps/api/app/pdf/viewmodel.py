from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TypedDict


class InvoiceRow(TypedDict):
    id: str
    org_id: str
    client_id: str
    invoice_number: str
    status: str
    pay_token: str
    due_date: str | None
    issued_at: str | None
    sent_at: str | None
    paid_at: str | None
    subtotal: str
    tax_rate: str
    tax_amount: str
    total: str
    notes: str | None


class ClientRow(TypedDict):
    id: str
    name: str
    email: str
    company: str | None


class OrgRow(TypedDict):
    id: str
    name: str
    slug: str


class LineItemRow(TypedDict):
    id: str
    invoice_id: str
    description: str
    quantity: str
    unit_price: str
    amount: str
    sort_order: int


@dataclass(frozen=True)
class LineItemViewModel:
    description: str
    quantity: str
    unit_price_formatted: str
    amount_formatted: str


@dataclass(frozen=True)
class InvoicePdfViewModel:
    invoice_number: str
    invoice_status: str
    is_void: bool
    client_name: str
    client_email: str
    client_company: str | None
    org_name: str
    total_formatted: str
    subtotal_formatted: str
    tax_formatted: str
    tax_rate_formatted: str
    due_date_formatted: str | None
    issued_at_formatted: str | None
    paid_at_formatted: str | None
    notes: str | None
    line_items: list[LineItemViewModel] = field(default_factory=list)


def format_currency(db_value: str) -> str:
    try:
        value = Decimal(db_value)
    except (InvalidOperation, ValueError):
        return "$0.00"
    return f"${value:,.2f}"


def format_date(iso_string: str | None) -> str | None:
    if not iso_string:
        return None
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(iso_string[:10], "%Y-%m-%d").replace(tzinfo=UTC)
            return dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            return None


def format_tax_rate(db_value: str) -> str:
    try:
        value = (Decimal(db_value) * 100).normalize()
        if value == value.to_integral_value():
            return f"{int(value)}%"
        return f"{value}%"
    except (InvalidOperation, ValueError):
        return "0%"


def format_quantity(db_value: str) -> str:
    try:
        value = Decimal(db_value)
        if value == value.to_integral_value():
            return str(int(value))
        return str(value.normalize())
    except (InvalidOperation, ValueError):
        return db_value


def build_pdf_view_model(
    invoice: InvoiceRow,
    client: ClientRow,
    org: OrgRow,
    line_items: list[LineItemRow],
    *,
    is_void: bool = False,
) -> InvoicePdfViewModel:
    item_vms = [
        LineItemViewModel(
            description=item["description"],
            quantity=format_quantity(str(item["quantity"])),
            unit_price_formatted=format_currency(str(item["unit_price"])),
            amount_formatted=format_currency(str(item["amount"])),
        )
        for item in sorted(line_items, key=lambda i: i["sort_order"])
    ]

    return InvoicePdfViewModel(
        invoice_number=invoice["invoice_number"],
        invoice_status=invoice["status"],
        is_void=is_void,
        client_name=client["name"],
        client_email=client["email"],
        client_company=client.get("company"),
        org_name=org["name"],
        total_formatted=format_currency(invoice["total"]),
        subtotal_formatted=format_currency(invoice["subtotal"]),
        tax_formatted=format_currency(invoice["tax_amount"]),
        tax_rate_formatted=format_tax_rate(invoice["tax_rate"]),
        due_date_formatted=format_date(invoice.get("due_date")),
        issued_at_formatted=format_date(invoice.get("issued_at")),
        paid_at_formatted=format_date(invoice.get("paid_at")),
        notes=invoice.get("notes"),
        line_items=item_vms,
    )
