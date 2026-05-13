from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import OrgUser, SupabaseDep
from app.exceptions import NotFoundError
from app.repositories import invoices as repo
from app.repositories._helpers import utc_now
from app.schemas.base import BaseResponse
from app.schemas.invoices import (
    CreateInvoice,
    InvoiceListFilters,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceStatus,
    UpdateInvoiceDraft,
    VoidInvoiceRequest,
)
from app.services import invoices as invoice_service
from app.utils.notification_log import write_audit
from app.utils.status_machine import assert_transition

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/")
async def create_invoice(
    body: CreateInvoice,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await invoice_service.create_invoice(db, org_id=ctx.org_id, payload=body)
    return BaseResponse(success=True, data=invoice)


@router.get("/")
async def list_invoices(
    ctx: OrgUser,
    db: SupabaseDep,
    status: InvoiceStatus | None = None,
    client_id: UUID | None = None,
    project_id: UUID | None = None,
    issue_date_from: date | None = None,
    issue_date_to: date | None = None,
    due_date_from: date | None = None,
    due_date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BaseResponse[InvoiceListResponse]:
    filters = InvoiceListFilters(
        status=status,
        client_id=client_id,
        project_id=project_id,
        issue_date_from=issue_date_from,
        issue_date_to=issue_date_to,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        limit=limit,
        offset=offset,
    )
    result = await invoice_service.list_invoices(db, org_id=ctx.org_id, filters=filters)
    return BaseResponse(success=True, data=result)


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await invoice_service.get_invoice_detail(db, org_id=ctx.org_id, invoice_id=invoice_id)
    return BaseResponse(success=True, data=invoice)


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: UUID,
    body: UpdateInvoiceDraft,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await invoice_service.update_draft_invoice(
        db,
        org_id=ctx.org_id,
        invoice_id=invoice_id,
        payload=body,
    )
    return BaseResponse(success=True, data=invoice)


@router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await invoice_service.send_invoice(db, org_id=ctx.org_id, invoice_id=invoice_id)
    return BaseResponse(success=True, data=invoice)


@router.post("/{invoice_id}/void")
async def void_invoice(
    invoice_id: UUID,
    body: VoidInvoiceRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[InvoiceResponse]:
    invoice = await repo.get_invoice(db, org_id=ctx.org_id, invoice_id=invoice_id)
    if invoice is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")

    assert_transition(invoice.status, "void")

    updated = await repo.void_invoice(
        db,
        org_id=ctx.org_id,
        invoice_id=invoice_id,
        voided_at=utc_now(),
    )

    await write_audit(
        db,
        invoice_id=invoice_id,
        event="invoice_voided",
        note=body.reason,
        org_id=ctx.org_id,
        user_id=ctx.user_id,
    )

    return BaseResponse(success=True, data=updated)
