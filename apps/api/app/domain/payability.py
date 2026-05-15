from dataclasses import dataclass

from app.schemas.invoices import InvoiceStatus


@dataclass(frozen=True)
class PayabilityInput:
    status: str
    amount_due_cents: int
    paid_at: object | None = None
    voided_at: object | None = None
    stripe_account_id: str | None = None
    stripe_payments_enabled: bool | None = None


@dataclass(frozen=True)
class PayabilityResult:
    is_payable: bool
    not_payable_reason: str | None = None


def evaluate_invoice_payability(invoice: PayabilityInput) -> PayabilityResult:
    try:
        status = InvoiceStatus(str(invoice.status).strip().lower())
    except ValueError:
        return PayabilityResult(False, "not_public")

    if status is InvoiceStatus.PAID or invoice.paid_at is not None:
        return PayabilityResult(False, "already_paid")
    if status is InvoiceStatus.VOID or invoice.voided_at is not None:
        return PayabilityResult(False, "void")
    if status is InvoiceStatus.DISPUTED:
        return PayabilityResult(False, "disputed")
    if invoice.amount_due_cents <= 0:
        return PayabilityResult(False, "no_amount_due")
    if status not in {InvoiceStatus.SENT, InvoiceStatus.LOCKED}:
        return PayabilityResult(False, "not_payable_status")
    if not invoice.stripe_account_id or not invoice.stripe_account_id.strip():
        return PayabilityResult(False, "payments_unavailable")
    if invoice.stripe_payments_enabled is False:
        return PayabilityResult(False, "payments_unavailable")

    return PayabilityResult(True)
