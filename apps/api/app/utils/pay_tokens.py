from uuid import UUID, uuid4

from app.schemas.invoices import InvoiceStatus

PayTokenInput = UUID | str

PUBLIC_INVOICE_STATUSES = frozenset(
    {
        InvoiceStatus.SENT,
        InvoiceStatus.LOCKED,
        InvoiceStatus.PAID,
        InvoiceStatus.DISPUTED,
        InvoiceStatus.RESOLVED,
    }
)


def generate_pay_token() -> UUID:
    return uuid4()


def normalize_pay_token(raw_token: object) -> UUID:
    if isinstance(raw_token, UUID):
        return raw_token
    if not isinstance(raw_token, str):
        raise ValueError("invalid pay token")

    token = raw_token.strip()
    if not token:
        raise ValueError("invalid pay token")

    try:
        return UUID(token)
    except ValueError:
        raise ValueError("invalid pay token") from None


def is_public_invoice_status(status: InvoiceStatus | str) -> bool:
    if isinstance(status, InvoiceStatus):
        normalized = status
    else:
        try:
            normalized = InvoiceStatus(str(status).strip().lower())
        except ValueError:
            return False

    return normalized in PUBLIC_INVOICE_STATUSES
