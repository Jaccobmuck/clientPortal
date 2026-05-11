from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CreateProjectRequest(BaseModel):
    client_id: UUID
    name: str = Field(min_length=1)
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if self.name is None and self.description is None:
            raise ValueError("at least one of 'name' or 'description' is required")
        return self


class UpdateStatusRequest(BaseModel):
    status: ProjectStatus


class ProjectResponse(BaseModel):
    id: UUID
    org_id: UUID
    client_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
