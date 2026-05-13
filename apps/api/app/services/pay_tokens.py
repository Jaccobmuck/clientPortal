from typing import NoReturn
from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.exceptions import NotFoundError
from app.repositories import invoices as invoice_repo
from app.schemas.invoices import InvoiceResponse
from app.utils.pay_tokens import is_public_invoice_status, normalize_pay_token


def _raise_public_invoice_unavailable() -> NoReturn:
    raise NotFoundError("invoice not found", code="invoice_not_found")


async def lookup_public_invoice_by_token(
    db: AsyncPostgrestClient, *, raw_token: object
) -> InvoiceResponse:
    try:
        pay_token = normalize_pay_token(raw_token)
    except ValueError:
        _raise_public_invoice_unavailable()

    invoice = await invoice_repo.get_invoice_by_pay_token(db, pay_token=pay_token)
    if invoice is None or not is_public_invoice_status(invoice.status):
        _raise_public_invoice_unavailable()

    return invoice


async def rotate_invoice_pay_token(
    db: AsyncPostgrestClient, *, org_id: UUID, invoice_id: UUID
) -> UUID:
    pay_token = await invoice_repo.rotate_invoice_pay_token(
        db, org_id=org_id, invoice_id=invoice_id
    )
    if pay_token is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return pay_token


async def invalidate_invoice_pay_token(
    db: AsyncPostgrestClient, *, org_id: UUID, invoice_id: UUID
) -> UUID:
    pay_token = await invoice_repo.invalidate_pay_token(db, org_id=org_id, invoice_id=invoice_id)
    if pay_token is None:
        raise NotFoundError("invoice not found", code="invoice_not_found")
    return pay_token
