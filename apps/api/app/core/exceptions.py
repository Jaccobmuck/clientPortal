from app.exceptions import ConflictError


class InvoiceStatusError(ConflictError):
    _default_message = "Invalid invoice status transition"
    _default_code = "invoice_status_error"
