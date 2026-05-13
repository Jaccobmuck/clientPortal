import pytest

from app.core.exceptions import InvoiceStatusError
from app.exceptions import ConflictError
from app.schemas.invoices import InvoiceStatus
from app.utils.status_machine import (
    assert_invoice_editable,
    assert_valid_transition,
    can_transition,
    is_invoice_editable,
)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (InvoiceStatus.DRAFT, InvoiceStatus.SENT),
        (InvoiceStatus.DRAFT, InvoiceStatus.VOID),
        (InvoiceStatus.SENT, InvoiceStatus.LOCKED),
        (InvoiceStatus.SENT, InvoiceStatus.DISPUTED),
        (InvoiceStatus.SENT, InvoiceStatus.VOID),
        (InvoiceStatus.LOCKED, InvoiceStatus.PAID),
        (InvoiceStatus.LOCKED, InvoiceStatus.DISPUTED),
        (InvoiceStatus.LOCKED, InvoiceStatus.VOID),
        (InvoiceStatus.DISPUTED, InvoiceStatus.RESOLVED),
        (InvoiceStatus.DISPUTED, InvoiceStatus.VOID),
        (InvoiceStatus.RESOLVED, InvoiceStatus.PAID),
        (InvoiceStatus.RESOLVED, InvoiceStatus.VOID),
    ],
)
def test_valid_invoice_status_transitions(
    from_status: InvoiceStatus,
    to_status: InvoiceStatus,
) -> None:
    assert can_transition(from_status, to_status)
    assert_valid_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (InvoiceStatus.DRAFT, InvoiceStatus.PAID),
        (InvoiceStatus.SENT, InvoiceStatus.PAID),
        (InvoiceStatus.LOCKED, InvoiceStatus.SENT),
        (InvoiceStatus.PAID, InvoiceStatus.VOID),
        (InvoiceStatus.PAID, InvoiceStatus.SENT),
        (InvoiceStatus.VOID, InvoiceStatus.DRAFT),
        (InvoiceStatus.VOID, InvoiceStatus.PAID),
        (InvoiceStatus.RESOLVED, InvoiceStatus.SENT),
    ],
)
def test_invalid_invoice_status_transitions(
    from_status: InvoiceStatus,
    to_status: InvoiceStatus,
) -> None:
    assert not can_transition(from_status, to_status)
    with pytest.raises(InvoiceStatusError):
        assert_valid_transition(from_status, to_status)


@pytest.mark.parametrize("terminal_status", [InvoiceStatus.PAID, InvoiceStatus.VOID])
def test_terminal_invoice_statuses_have_no_outgoing_transitions(
    terminal_status: InvoiceStatus,
) -> None:
    assert all(
        not can_transition(terminal_status, target_status)
        for target_status in InvoiceStatus
    )


def test_status_transition_normalizes_strings() -> None:
    assert can_transition(" draft ", "SENT")


def test_status_transition_rejects_unknown_statuses() -> None:
    assert not can_transition("unknown", InvoiceStatus.SENT)
    assert not can_transition(InvoiceStatus.DRAFT, "unknown")


def test_draft_invoice_is_editable() -> None:
    assert is_invoice_editable(InvoiceStatus.DRAFT)
    assert_invoice_editable(InvoiceStatus.DRAFT)


@pytest.mark.parametrize(
    "status",
    [
        InvoiceStatus.SENT,
        InvoiceStatus.LOCKED,
        InvoiceStatus.PAID,
        InvoiceStatus.DISPUTED,
        InvoiceStatus.RESOLVED,
        InvoiceStatus.VOID,
    ],
)
def test_non_draft_invoices_are_not_editable(status: InvoiceStatus) -> None:
    assert not is_invoice_editable(status)
    with pytest.raises(ConflictError):
        assert_invoice_editable(status)
