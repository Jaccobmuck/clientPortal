from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class BaseResponse[T](BaseModel):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaginatedResponse[T](BaseModel):
    success: bool
    data: list[T]
    error: ErrorDetail | None = None
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pagination: PaginationMeta
