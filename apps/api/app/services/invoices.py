import re
from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.repositories import clients as clients_repo
from app.repositories import invoices as repo
from app.repositories._helpers import utc_now
from app.schemas.invoices import (
    CreateInvoice,
    InvoiceListFilters,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceStatus,
    UpdateInvoiceDraft,
)
from app.utils.queues import enqueue_email, enqueue_pdf
from app.utils.status_machine import assert_invoice_editable, assert_transition

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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

    assert_invoice_editable(existing.status)

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


async def send_invoice(
    db: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
) -> InvoiceResponse:
    invoice = await repo.get_invoice(db, org_id=org_id, invoice_id=invoice_id)
    if invoice is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")

    if invoice.status == InvoiceStatus.SENT:
        return invoice

    if invoice.status != InvoiceStatus.DRAFT:
        raise ConflictError(
            f"cannot send invoice with status '{invoice.status}'",
            code="invalid_status_transition",
        )

    if not invoice.line_items:
        raise ConflictError("invoice has no line items", code="no_line_items")

    if invoice.total_cents <= 0:
        raise ConflictError(
            "invoice total must be greater than zero",
            code="invalid_total",
        )

    client = await clients_repo.get_client(db, org_id=org_id, client_id=invoice.client_id)
    if client is None:
        raise NotFoundError("client not found", code="client_not_found")
    if not client.email or not _EMAIL_RE.match(client.email):
        raise ValidationError(
            "client must have a valid email address",
            code="invalid_client_email",
        )

    assert_transition(invoice.status, InvoiceStatus.SENT)

    updated = await repo.send_invoice(
        db,
        org_id=org_id,
        invoice_id=invoice_id,
        sent_at=utc_now(),
    )
    if updated is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")

    await enqueue_pdf(db, invoice_id=invoice_id, org_id=org_id)
    await enqueue_email(db, invoice_id=invoice_id, org_id=org_id)

    return updated
