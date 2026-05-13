from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories import invoices as repo
from app.schemas.invoices import (
    CreateInvoice,
    InvoiceListFilters,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceStatus,
    UpdateInvoiceDraft,
)


async def create_invoice(
    db: AsyncPostgrestClient,
    *,
    org_id: UUID,
    payload: CreateInvoice,
) -> InvoiceResponse:
    await repo.validate_client_ownership(db, org_id=org_id, client_id=payload.client_id)
    if payload.project_id is not None:
        await repo.validate_project_ownership(db, org_id=org_id, project_id=payload.project_id)

    data = payload.model_dump()
    return await repo.create_invoice(db, org_id=org_id, data=data)


async def list_invoices(
    db: AsyncPostgrestClient,
    *,
    org_id: UUID,
    filters: InvoiceListFilters,
) -> InvoiceListResponse:
    status_value = filters.status.value if filters.status else None

    items = await repo.list_invoices(
        db,
        org_id=org_id,
        limit=filters.limit,
        offset=filters.offset,
        client_id=filters.client_id,
        project_id=filters.project_id,
        status=status_value,
        issue_date_from=filters.issue_date_from,
        issue_date_to=filters.issue_date_to,
        due_date_from=filters.due_date_from,
        due_date_to=filters.due_date_to,
    )

    total = await repo.count_invoices(
        db,
        org_id=org_id,
        client_id=filters.client_id,
        project_id=filters.project_id,
        status=status_value,
        issue_date_from=filters.issue_date_from,
        issue_date_to=filters.issue_date_to,
        due_date_from=filters.due_date_from,
        due_date_to=filters.due_date_to,
    )

    return InvoiceListResponse(
        items=items,
        limit=filters.limit,
        offset=filters.offset,
        total=total,
    )


async def get_invoice_detail(
    db: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
) -> InvoiceResponse:
    invoice = await repo.get_invoice(db, org_id=org_id, invoice_id=invoice_id)
    if invoice is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return invoice


async def update_draft_invoice(
    db: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    payload: UpdateInvoiceDraft,
) -> InvoiceResponse:
    existing = await repo.get_invoice(db, org_id=org_id, invoice_id=invoice_id)
    if existing is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")

    if existing.status != InvoiceStatus.DRAFT:
        raise ConflictError("only draft invoices can be edited", code="invoice_locked")

    fields = payload.model_dump(exclude_unset=True)

    final_client_id = fields.get("client_id", existing.client_id)
    if "client_id" in fields:
        await repo.validate_client_ownership(db, org_id=org_id, client_id=final_client_id)

    final_project_id = fields.get("project_id", existing.project_id)
    if "project_id" in fields and final_project_id is not None:
        await repo.validate_project_ownership(db, org_id=org_id, project_id=final_project_id)

    final_issue_date = fields.get("issue_date", existing.issue_date)
    final_due_date = fields.get("due_date", existing.due_date)
    if (
        final_issue_date is not None
        and final_due_date is not None
        and final_due_date < final_issue_date
    ):
        raise ValidationError(
            "due_date must be greater than or equal to issue_date",
            code="invalid_dates",
        )

    db_payload: dict[str, object] = {}
    if "client_id" in fields:
        db_payload["client_id"] = str(final_client_id)
    if "project_id" in fields:
        db_payload["project_id"] = str(final_project_id) if final_project_id else None
    if "issue_date" in fields:
        db_payload["issued_at"] = fields["issue_date"].isoformat()
    if "due_date" in fields:
        db_payload["due_date"] = fields["due_date"].isoformat()
    if "memo" in fields:
        db_payload["notes"] = fields["memo"]

    line_items_input = fields.get("line_items")

    if line_items_input is not None:
        await repo.delete_invoice_line_items(db, invoice_id=invoice_id)
        await repo.insert_line_items(db, invoice_id=invoice_id, line_items=line_items_input)
        subtotal, tax, total = repo.compute_line_totals(line_items_input)
        await repo.update_invoice_totals(
            db,
            org_id=org_id,
            invoice_id=invoice_id,
            subtotal_cents=subtotal,
            tax_cents=tax,
            total_cents=total,
        )

    result = await repo.update_invoice_fields(
        db, org_id=org_id, invoice_id=invoice_id, payload=db_payload
    )
    if result is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return result
