import logging
from typing import NoReturn

from postgrest import AsyncPostgrestClient

from app.domain.payability import PayabilityInput, evaluate_invoice_payability
from app.exceptions import NotFoundError
from app.repositories import invoices as invoice_repo
from app.schemas.pay import (
    PublicClientSummary,
    PublicInvoiceLineItem,
    PublicInvoiceView,
    PublicOrgBranding,
)
from app.services.storage import PdfStorageService
from app.utils.pay_tokens import normalize_pay_token

logger = logging.getLogger(__name__)


def _public_invoice_not_found() -> NoReturn:
    raise NotFoundError("Invoice not found", code="invoice_not_found")


class PayPortalService:
    def __init__(
        self,
        db: AsyncPostgrestClient,
        *,
        pdf_storage: PdfStorageService,
    ) -> None:
        self._db = db
        self._pdf_storage = pdf_storage

    async def get_public_invoice_view(self, *, raw_token: object) -> PublicInvoiceView:
        try:
            token = normalize_pay_token(raw_token)
        except ValueError:
            _public_invoice_not_found()

        invoice = await invoice_repo.get_public_invoice_by_pay_token(self._db, token=token)
        if invoice is None or not invoice.is_public_viewable:
            _public_invoice_not_found()

        pdf_url = None
        if invoice.pdf_storage_path:
            try:
                pdf_url = await self._pdf_storage.create_signed_invoice_pdf_url(
                    invoice.pdf_storage_path
                )
            except Exception:
                logger.warning(
                    "failed to sign public invoice PDF [invoice_id=%s]",
                    invoice.invoice_id,
                    exc_info=True,
                )

        payability = evaluate_invoice_payability(
            PayabilityInput(
                status=invoice.status,
                amount_due_cents=invoice.amount_due_cents,
                paid_at=invoice.paid_at,
                voided_at=invoice.voided_at,
                stripe_account_id=invoice.stripe_account_id,
                stripe_payments_enabled=invoice.stripe_payments_enabled,
            )
        )

        return PublicInvoiceView(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            status=invoice.status,
            issued_at=invoice.issued_at,
            due_at=invoice.due_at,
            subtotal_cents=invoice.subtotal_cents,
            tax_cents=invoice.tax_cents,
            discount_cents=invoice.discount_cents,
            total_cents=invoice.total_cents,
            amount_paid_cents=invoice.amount_paid_cents,
            amount_due_cents=invoice.amount_due_cents,
            currency=invoice.currency,
            is_payable=payability.is_payable,
            not_payable_reason=payability.not_payable_reason,
            org=PublicOrgBranding(
                name=invoice.org_name,
                logo_url=invoice.org_logo_url,
                brand_color=invoice.org_brand_color,
                support_email=invoice.org_support_email,
            ),
            client=PublicClientSummary(
                name=invoice.client_name,
                email=invoice.client_email,
            ),
            line_items=[
                PublicInvoiceLineItem(
                    description=item.description,
                    quantity=item.quantity,
                    unit_amount_cents=item.unit_amount_cents,
                    line_total_cents=item.line_total_cents,
                )
                for item in invoice.line_items
            ],
            pdf_url=pdf_url,
        )
