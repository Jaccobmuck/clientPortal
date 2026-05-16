from typing import NoReturn

from postgrest import AsyncPostgrestClient

from app.domain.payability import PayabilityInput, evaluate_invoice_payability
from app.exceptions import ConflictError, NotFoundError
from app.repositories import invoices as invoice_repo
from app.schemas.pay import CheckoutSessionResponse
from app.services.stripe_checkout import StripeCheckoutService
from app.utils.pay_tokens import normalize_pay_token


def _public_invoice_not_found() -> NoReturn:
    raise NotFoundError("Invoice not found", code="invoice_not_found")


_NOT_PAYABLE_MESSAGES = {
    "already_paid": "invoice is already paid",
    "void": "invoice is void",
    "disputed": "invoice is disputed",
    "no_amount_due": "invoice has no amount due",
    "not_payable_status": "invoice is not payable",
    "payments_unavailable": "payments are unavailable for this invoice",
}


class PayCheckoutService:
    def __init__(
        self,
        db: AsyncPostgrestClient,
        *,
        stripe_checkout: StripeCheckoutService,
    ) -> None:
        self._db = db
        self._stripe_checkout = stripe_checkout

    async def create_checkout_session(self, *, raw_token: object) -> CheckoutSessionResponse:
        try:
            token = normalize_pay_token(raw_token)
        except ValueError:
            _public_invoice_not_found()

        invoice = await invoice_repo.get_public_invoice_by_pay_token(self._db, token=token)
        if invoice is None or not invoice.is_public_viewable:
            _public_invoice_not_found()

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
        if not payability.is_payable:
            reason = payability.not_payable_reason or "not_payable_status"
            raise ConflictError(
                _NOT_PAYABLE_MESSAGES.get(reason, "invoice is not payable"),
                code=f"invoice_{reason}",
            )

        connected_account_id = (
            invoice.stripe_account_id.strip() if invoice.stripe_account_id else None
        )
        if connected_account_id is None:
            raise ConflictError(
                "payments are unavailable for this invoice",
                code="invoice_payments_unavailable",
            )

        result = await self._stripe_checkout.create_invoice_checkout_session(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            pay_token=invoice.pay_token,
            org_id=invoice.org_id,
            connected_account_id=connected_account_id,
            amount_due_cents=invoice.amount_due_cents,
            currency=invoice.currency,
            client_email=invoice.client_email,
        )
        return CheckoutSessionResponse(
            session_id=result.session_id,
            checkout_url=result.checkout_url,
        )
