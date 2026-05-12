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


class LineItemInput(BaseModel):
    description: str = Field(min_length=1)
    quantity: str = Field(default="1")
    unit_price: int = Field(gt=0)
    sort_order: int = Field(default=0, ge=0)

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


class LineItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    description: str
    quantity: str
    unit_price: int
    amount: int
    sort_order: int


class CreateInvoiceRequest(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    due_date: date | None = None
    tax_rate: int = Field(default=0, ge=0, le=10000)
    notes: str | None = Field(default=None, max_length=2000)
    line_items: list[LineItemInput] = Field(default_factory=list)


class UpdateInvoiceRequest(BaseModel):
    client_id: UUID | None = None
    project_id: UUID | None = None
    due_date: date | None = None
    tax_rate: int | None = Field(default=None, ge=0, le=10000)
    notes: str | None = None
    line_items: list[LineItemInput] | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if all(
            v is None
            for v in (
                self.client_id,
                self.project_id,
                self.due_date,
                self.tax_rate,
                self.notes,
                self.line_items,
            )
        ):
            raise ValueError("at least one field is required")
        return self


class VoidInvoiceRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


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
