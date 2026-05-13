from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.repositories import invoices as repo
from app.schemas.invoices import (
    CreateInvoice,
    InvoiceListFilters,
    InvoiceListResponse,
    InvoiceResponse,
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
