import logging
import os
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, UploadFile
from supabase import AsyncClient

from app.core.deps import OrgUser, SupabaseDep, get_db
from app.core.settings import settings
from app.exceptions import InternalError, NotFoundError, ValidationError
from app.repositories import expenses as repo
from app.schemas.base import BaseResponse
from app.schemas.expenses import (
    CreateExpenseRequest,
    ExpenseResponse,
    UpdateExpenseRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expenses", tags=["expenses"])

_ALLOWED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".pdf"})


@router.post("/")
async def create_expense(
    body: CreateExpenseRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ExpenseResponse]:
    data = body.model_dump()
    expense = await repo.create_expense(db, org_id=ctx.org_id, data=data)
    return BaseResponse(success=True, data=expense)


@router.get("/")
async def list_expenses(
    ctx: OrgUser,
    db: SupabaseDep,
    project_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BaseResponse[list[ExpenseResponse]]:
    clamped_limit = min(limit, 100)
    expenses = await repo.list_expenses(
        db,
        org_id=ctx.org_id,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
        limit=clamped_limit,
        offset=offset,
    )
    return BaseResponse(success=True, data=expenses)


@router.get("/{expense_id}")
async def get_expense(
    expense_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ExpenseResponse]:
    expense = await repo.get_expense(db, org_id=ctx.org_id, expense_id=expense_id)
    if expense is None:
        raise NotFoundError("expense not found", code="expense_not_found")
    return BaseResponse(success=True, data=expense)


@router.patch("/{expense_id}")
async def update_expense(
    expense_id: UUID,
    body: UpdateExpenseRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ExpenseResponse]:
    fields = body.model_dump(exclude_unset=True)
    expense = await repo.update_expense(
        db,
        org_id=ctx.org_id,
        expense_id=expense_id,
        data=fields,
    )
    if expense is None:
        raise NotFoundError("expense not found", code="expense_not_found")
    return BaseResponse(success=True, data=expense)


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[None]:
    deleted = await repo.soft_delete_expense(
        db, org_id=ctx.org_id, expense_id=expense_id
    )
    if not deleted:
        raise NotFoundError("expense not found", code="expense_not_found")
    return BaseResponse(success=True, data=None)


@router.post("/{expense_id}/receipt")
async def upload_receipt(
    expense_id: UUID,
    file: UploadFile,
    ctx: OrgUser,
    db: SupabaseDep,
    supabase: AsyncClient = Depends(get_db),
) -> BaseResponse[ExpenseResponse]:
    expense = await repo.get_expense(db, org_id=ctx.org_id, expense_id=expense_id)
    if expense is None:
        raise NotFoundError("expense not found", code="expense_not_found")

    if file.content_type not in settings.RECEIPT_ALLOWED_TYPES:
        raise ValidationError(
            f"file type '{file.content_type}' not allowed",
            code="invalid_file_type",
        )

    original_name = file.filename or "upload"
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"file extension '{ext}' not allowed",
            code="invalid_file_extension",
        )

    max_bytes = settings.RECEIPT_MAX_SIZE_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(
                f"file exceeds {settings.RECEIPT_MAX_SIZE_MB}MB limit",
                code="file_too_large",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    safe_filename = f"{uuid4()}{ext}"
    storage_path = f"{ctx.org_id}/{expense_id}/{safe_filename}"

    bucket = supabase.storage.from_(settings.RECEIPT_BUCKET)
    await bucket.upload(
        storage_path,
        file_bytes,
        {"content-type": file.content_type, "upsert": "true"},
    )

    public_url = bucket.get_public_url(storage_path)

    updated = await repo.update_receipt_url(
        db,
        org_id=ctx.org_id,
        expense_id=expense_id,
        url=public_url,
    )
    if updated is None:
        try:
            await bucket.remove([storage_path])
        except Exception:
            logger.warning("failed to clean up uploaded file: %s", storage_path)
        raise InternalError("failed to update receipt URL after upload")

    return BaseResponse(success=True, data=updated)
