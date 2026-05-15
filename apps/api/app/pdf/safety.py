from __future__ import annotations


class PdfSafetyError(Exception):
    def __init__(self, message: str, *, permanent: bool = True) -> None:
        super().__init__(message)
        self.permanent = permanent


RENDERABLE_STATUSES = {"sent", "locked", "paid", "disputed", "resolved", "void"}
SKIP_STATUSES = {"draft"}


def validate_pdf_status(status: str) -> None:
    normalized = status.lower().strip()
    if normalized in SKIP_STATUSES:
        raise PdfSafetyError(f"Cannot render PDF for invoice with status: {status}")
    if normalized not in RENDERABLE_STATUSES:
        raise PdfSafetyError(f"Unknown invoice status for PDF rendering: {status}")


def is_void_invoice(status: str) -> bool:
    return status.lower().strip() == "void"
