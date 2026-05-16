from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PublicOrgBranding(BaseModel):
    name: str
    logo_url: str | None = None
    brand_color: str | None = None
    support_email: str | None = None


class PublicClientSummary(BaseModel):
    name: str
    email: str | None = None


class PublicInvoiceLineItem(BaseModel):
    description: str
    quantity: str
    unit_amount_cents: int = Field(ge=0)
    line_total_cents: int = Field(ge=0)


class PublicInvoiceView(BaseModel):
    invoice_id: UUID
    invoice_number: str
    status: str
    issued_at: datetime | None = None
    due_at: date | None = None

    subtotal_cents: int = Field(ge=0)
    tax_cents: int = Field(ge=0)
    discount_cents: int = Field(ge=0)
    total_cents: int = Field(ge=0)
    amount_paid_cents: int = Field(ge=0)
    amount_due_cents: int = Field(ge=0)
    currency: str

    is_payable: bool
    not_payable_reason: str | None = None

    org: PublicOrgBranding
    client: PublicClientSummary
    line_items: list[PublicInvoiceLineItem]

    pdf_url: str | None = None


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str
