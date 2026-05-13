from uuid import UUID, uuid4

import pytest

from app.schemas.invoices import InvoiceStatus
from app.utils.pay_tokens import (
    generate_pay_token,
    is_public_invoice_status,
    normalize_pay_token,
)


def test_generate_pay_token_returns_uuid_v4() -> None:
    token = generate_pay_token()

    assert isinstance(token, UUID)
    assert token.version == 4


def test_normalize_pay_token_accepts_valid_uuid_string() -> None:
    token = uuid4()

    assert normalize_pay_token(str(token)) == token


def test_normalize_pay_token_accepts_uuid() -> None:
    token = uuid4()

    assert normalize_pay_token(token) == token


@pytest.mark.parametrize("raw_token", ["", "not-a-token", "1234", object()])
def test_normalize_pay_token_rejects_malformed_token(raw_token: object) -> None:
    with pytest.raises(ValueError, match="invalid pay token"):
        normalize_pay_token(raw_token)


@pytest.mark.parametrize(
    "status",
    [
        InvoiceStatus.SENT,
        InvoiceStatus.LOCKED,
        InvoiceStatus.PAID,
        InvoiceStatus.DISPUTED,
        InvoiceStatus.RESOLVED,
        " sent ",
        "LOCKED",
    ],
)
def test_is_public_invoice_status_allows_client_visible_statuses(
    status: InvoiceStatus | str,
) -> None:
    assert is_public_invoice_status(status)


@pytest.mark.parametrize(
    "status",
    [InvoiceStatus.DRAFT, InvoiceStatus.VOID, InvoiceStatus.OVERDUE, "unknown"],
)
def test_is_public_invoice_status_rejects_private_or_unknown_statuses(
    status: InvoiceStatus | str,
) -> None:
    assert not is_public_invoice_status(status)
