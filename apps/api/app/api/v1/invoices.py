from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import OrgUser, SupabaseDep
from app.exceptions import NotFoundError
from app.repositories import invoices as repo
from app.schemas.base import BaseResponse
from app.schemas.invoices import (
    CreateInvoiceRequest,
    InvoiceResponse,
    InvoiceStatus,
    UpdateInvoiceRequest,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/")
async def create_invoice(
    body: CreateInvoiceRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    data = body.model_dump()
    invoice = await repo.create_invoice(db, org_id=ctx.org_id, data=data)
    return BaseResponse(success=True, data=invoice)


@router.get("/")
async def list_invoices(
    ctx: OrgUser,
    db: SupabaseDep,
    client_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BaseResponse[list[InvoiceResponse]]:
    clamped_limit = min(limit, 100)
    invoices = await repo.list_invoices(
        db,
        org_id=ctx.org_id,
        client_id=client_id,
        status=status.value if status else None,
        limit=clamped_limit,
        offset=offset,
    )
    return BaseResponse(success=True, data=invoices)


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await repo.get_invoice(db, org_id=ctx.org_id, invoice_id=invoice_id)
    if invoice is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return BaseResponse(success=True, data=invoice)


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: UUID,
    body: UpdateInvoiceRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    fields = body.model_dump(exclude_unset=True)
    invoice = await repo.update_invoice(
        db,
        org_id=ctx.org_id,
        invoice_id=invoice_id,
        data=fields,
    )
    if invoice is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return BaseResponse(success=True, data=invoice)
