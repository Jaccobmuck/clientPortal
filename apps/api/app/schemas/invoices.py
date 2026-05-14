from datetime import date, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    LOCKED = "locked"
    PAID = "paid"
    DISPUTED = "disputed"
    RESOLVED = "resolved"
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

        if (
            self.issue_date is not None
            and self.due_date is not None
            and self.due_date < self.issue_date
        ):
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
    description: str
    quantity: str
    unit_price_cents: int
    tax_rate_bp: int | None = None
    line_total_cents: int


class InvoiceResponse(BaseModel):
    id: UUID
    org_id: UUID
    client_id: UUID
    project_id: UUID | None
    invoice_number: str
    status: InvoiceStatus
    issue_date: date | None
    due_date: date | None
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    memo: str | None = None
    line_items: list[LineItemResponse]
    created_at: datetime
    updated_at: datetime


class QueueStatus(BaseModel):
    pdf: str
    email: str
    reminders: str


class InvoiceSendResponse(InvoiceResponse):
    send_event_id: UUID
    queue_status: QueueStatus


class InvoiceListItem(BaseModel):
    id: UUID
    client_id: UUID
    invoice_number: str
    status: InvoiceStatus
    issue_date: date | None
    due_date: date | None
    total_cents: int
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)
    total: int | None = Field(default=None, ge=0)


class InvoiceListFilters(BaseModel):
    status: InvoiceStatus | None = None
    client_id: UUID | None = None
    project_id: UUID | None = None
    issue_date_from: date | None = None
    issue_date_to: date | None = None
    due_date_from: date | None = None
    due_date_to: date | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_date_ranges(self) -> Self:
        if (
            self.issue_date_from is not None
            and self.issue_date_to is not None
            and self.issue_date_from > self.issue_date_to
        ):
            raise ValueError("issue_date_from must be less than or equal to issue_date_to")

        if (
            self.due_date_from is not None
            and self.due_date_to is not None
            and self.due_date_from > self.due_date_to
        ):
            raise ValueError("due_date_from must be less than or equal to due_date_to")

        return self


# ---------------------------------------------------------------------------
# Backward-compat aliases (import compatibility for existing routes/repos)
# ---------------------------------------------------------------------------

LineItemInput = LineItemIn
CreateInvoiceRequest = CreateInvoice
UpdateInvoiceRequest = UpdateInvoiceDraft
