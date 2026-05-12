from datetime import date, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    DISPUTED = "disputed"
    RESOLVED = "resolved"
    PAID = "paid"
    VOID = "void"
    OVERDUE = "overdue"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LineItemIn(BaseModel):
    description: str = Field(min_length=1)
    quantity: str = Field(default="1")
    unit_price_cents: int = Field(ge=0)
    tax_rate_bp: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("description", mode="before")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("quantity")
    @classmethod
    def _positive_quantity(cls, v: str) -> str:
        from decimal import Decimal, InvalidOperation

        try:
            d = Decimal(v)
        except InvalidOperation:
            raise ValueError("quantity must be a valid decimal number") from None
        if d <= 0:
            raise ValueError("quantity must be greater than 0")
        return v


class CreateInvoice(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    issue_date: date
    due_date: date
    line_items: list[LineItemIn] = Field(min_length=1)
    memo: str | None = None

    @model_validator(mode="after")
    def _due_after_issue(self) -> Self:
        if self.due_date < self.issue_date:
            raise ValueError("due_date must be greater than or equal to issue_date")
        return self


class UpdateInvoiceDraft(BaseModel):
    client_id: UUID | None = None
    project_id: UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    memo: str | None = None
    line_items: list[LineItemIn] | None = None

    @model_validator(mode="after")
    def _validate_partial(self) -> Self:
        if all(
            v is None
            for v in (
                self.client_id,
                self.project_id,
                self.issue_date,
                self.due_date,
                self.memo,
                self.line_items,
            )
        ):
            raise ValueError("at least one field is required")

        if self.line_items is not None and len(self.line_items) == 0:
            raise ValueError("line_items must not be empty when provided")

        if self.issue_date is not None and self.due_date is not None:
            if self.due_date < self.issue_date:
                raise ValueError("due_date must be greater than or equal to issue_date")

        return self


class VoidInvoiceRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LineItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    description: str
    quantity: str
    unit_price: int
    amount: int
    sort_order: int


class InvoiceResponse(BaseModel):
    id: UUID
    org_id: UUID
    client_id: UUID
    project_id: UUID | None
    invoice_number: str
    status: str
    pay_token: UUID
    due_date: date | None
    issued_at: datetime | None
    sent_at: datetime | None
    paid_at: datetime | None
    voided_at: datetime | None
    locked: bool
    subtotal: int
    tax_rate: int
    tax_amount: int
    total: int
    notes: str | None
    line_items: list[LineItemResponse]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Backward-compat aliases (import compatibility for existing routes/repos)
# ---------------------------------------------------------------------------

LineItemInput = LineItemIn
CreateInvoiceRequest = CreateInvoice
UpdateInvoiceRequest = UpdateInvoiceDraft
