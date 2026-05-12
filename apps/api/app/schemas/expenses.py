from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CreateExpenseRequest(BaseModel):
    project_id: UUID | None = None
    description: str = Field(min_length=1)
    amount: int = Field(gt=0)
    category: str | None = None
    incurred_at: date


class UpdateExpenseRequest(BaseModel):
    project_id: UUID | None = None
    description: str | None = Field(default=None, min_length=1)
    amount: int | None = Field(default=None, gt=0)
    category: str | None = None
    incurred_at: date | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if all(
            v is None
            for v in (
                self.project_id,
                self.description,
                self.amount,
                self.category,
                self.incurred_at,
            )
        ):
            raise ValueError("at least one field is required")
        return self


class ExpenseResponse(BaseModel):
    id: UUID
    org_id: UUID
    project_id: UUID | None
    description: str
    amount: int
    category: str | None
    receipt_url: str | None
    incurred_at: date
    created_at: datetime
    updated_at: datetime
