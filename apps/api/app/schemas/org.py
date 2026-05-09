from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.permissions import OrgRole

_SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$"


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(pattern=_SLUG_PATTERN)


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    slug: str | None = Field(default=None, pattern=_SLUG_PATTERN)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if self.name is None and self.slug is None:
            raise ValueError("at least one of 'name' or 'slug' is required")
        return self


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    owner_id: UUID
    created_at: datetime


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: OrgRole

    @field_validator("role")
    @classmethod
    def _reject_owner(cls, value: OrgRole) -> OrgRole:
        if value is OrgRole.OWNER:
            raise ValueError("owner role cannot be assigned via invite")
        return value


class MemberResponse(BaseModel):
    user_id: UUID
    email: str | None
    role: OrgRole
    joined_at: datetime
