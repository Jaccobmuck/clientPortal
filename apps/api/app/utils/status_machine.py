from app.core.exceptions import InvoiceStatusError
from app.exceptions import ConflictError
from app.schemas.invoices import InvoiceStatus

InvoiceStatusInput = InvoiceStatus | str

ALLOWED_TRANSITIONS: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset({InvoiceStatus.SENT, InvoiceStatus.VOID}),
    InvoiceStatus.SENT: frozenset(
        {InvoiceStatus.LOCKED, InvoiceStatus.DISPUTED, InvoiceStatus.VOID}
    ),
    InvoiceStatus.LOCKED: frozenset(
        {InvoiceStatus.PAID, InvoiceStatus.DISPUTED, InvoiceStatus.VOID}
    ),
    InvoiceStatus.DISPUTED: frozenset({InvoiceStatus.RESOLVED, InvoiceStatus.VOID}),
    InvoiceStatus.RESOLVED: frozenset({InvoiceStatus.PAID, InvoiceStatus.VOID}),
    InvoiceStatus.PAID: frozenset(),
    InvoiceStatus.VOID: frozenset(),
    # Preserved for import/filter compatibility with existing data. New lifecycle
    # transitions intentionally do not route through overdue.
    InvoiceStatus.OVERDUE: frozenset(),
}

VALID_TRANSITIONS: dict[str, list[str]] = {
    status.value: [target.value for target in targets]
    for status, targets in ALLOWED_TRANSITIONS.items()
}


def _normalize_status(status: InvoiceStatusInput) -> InvoiceStatus | None:
    if isinstance(status, InvoiceStatus):
        return status

    try:
        return InvoiceStatus(str(status).strip().lower())
    except ValueError:
        return None


def _display_status(status: InvoiceStatusInput) -> str:
    normalized = _normalize_status(status)
    if normalized is not None:
        return normalized.value
    return str(status)


def can_transition(from_status: InvoiceStatusInput, to_status: InvoiceStatusInput) -> bool:
    current = _normalize_status(from_status)
    target = _normalize_status(to_status)
    if current is None or target is None:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_valid_transition(from_status: InvoiceStatusInput, to_status: InvoiceStatusInput) -> None:
    if can_transition(from_status, to_status):
        return

    raise InvoiceStatusError(
        f"cannot transition from '{_display_status(from_status)}' "
        f"to '{_display_status(to_status)}'",
        code="invalid_status_transition",
    )


def is_invoice_editable(status: InvoiceStatusInput) -> bool:
    return _normalize_status(status) == InvoiceStatus.DRAFT


def assert_invoice_editable(status: InvoiceStatusInput) -> None:
    if is_invoice_editable(status):
        return

    raise ConflictError("only draft invoices can be edited", code="invoice_locked")


def assert_transition(current: InvoiceStatusInput, target: InvoiceStatusInput) -> None:
    assert_valid_transition(current, target)
