from __future__ import annotations

from app.pdf.renderer import render_pdf
from app.pdf.template_renderer import render_invoice_html
from app.pdf.viewmodel import InvoicePdfViewModel, LineItemViewModel


def create_fake_pdf_view_model(
    overrides: dict | None = None,
) -> InvoicePdfViewModel:
    defaults = {
        "invoice_number": "SMOKE-001",
        "invoice_status": "sent",
        "is_void": False,
        "client_name": "Smoke Test Client",
        "client_email": "smoke@example.com",
        "client_company": "Smoke Test Inc.",
        "org_name": "Freelio Smoke",
        "total_formatted": "$1,234.56",
        "subtotal_formatted": "$1,140.33",
        "tax_formatted": "$94.23",
        "tax_rate_formatted": "8%",
        "due_date_formatted": "December 31, 2026",
        "issued_at_formatted": "December 1, 2026",
        "paid_at_formatted": None,
        "notes": "This is a smoke test invoice.",
        "line_items": [
            LineItemViewModel(
                description="Website Design",
                quantity="1",
                unit_price_formatted="$800.00",
                amount_formatted="$800.00",
            ),
            LineItemViewModel(
                description="Consulting Hours",
                quantity="4.5",
                unit_price_formatted="$75.63",
                amount_formatted="$340.33",
            ),
        ],
    }
    if overrides:
        defaults.update(overrides)
    return InvoicePdfViewModel(**defaults)


def smoke_render_pdf() -> tuple[bytes, str]:
    vm = create_fake_pdf_view_model()
    html = render_invoice_html(vm)
    pdf_bytes = render_pdf(html)
    return pdf_bytes, "smoke_invoice.pdf"
