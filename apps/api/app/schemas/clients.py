from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class CreateClientRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    notes: str | None = None


class UpdateClientRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    phone: str | None = None
    company: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if all(
            v is None
            for v in (self.name, self.email, self.phone, self.company, self.notes)
        ):
            raise ValueError("at least one field is required")
        return self


class ClientResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    email: str
    phone: str | None
    company: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
