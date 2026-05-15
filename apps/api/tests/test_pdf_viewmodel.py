from app.pdf.viewmodel import (
    InvoicePdfViewModel,
    LineItemViewModel,
    build_pdf_view_model,
    format_currency,
    format_date,
    format_quantity,
    format_tax_rate,
)


def _fake_invoice():
    return {
        "id": "inv-001",
        "org_id": "org-001",
        "client_id": "client-001",
        "invoice_number": "INV-0001",
        "status": "sent",
        "pay_token": "tok-abc",
        "due_date": "2026-02-15",
        "issued_at": "2026-01-15T00:00:00Z",
        "sent_at": "2026-01-15T10:00:00Z",
        "paid_at": None,
        "subtotal": "1000.00",
        "tax_rate": "0.0800",
        "tax_amount": "80.00",
        "total": "1080.00",
        "notes": "Test invoice",
    }


def _fake_client():
    return {"id": "client-001", "name": "Acme Corp", "email": "billing@acme.com", "company": "Acme Inc."}


def _fake_org():
    return {"id": "org-001", "name": "Freelio Studio", "slug": "freelio-studio"}


def _fake_line_items():
    return [
        {
            "id": "li-1",
            "invoice_id": "inv-001",
            "description": "Design work",
            "quantity": "2",
            "unit_price": "500.00",
            "amount": "1000.00",
            "sort_order": 0,
        },
    ]


def test_format_currency_standard():
    assert format_currency("1250.00") == "$1,250.00"
    assert format_currency("0.50") == "$0.50"
    assert format_currency("99999.99") == "$99,999.99"
    assert format_currency("0") == "$0.00"


def test_format_currency_nan():
    assert format_currency("not-a-number") == "$0.00"


def test_format_date_iso():
    assert format_date("2026-01-15") == "January 15, 2026"
    assert format_date("2026-06-01T12:00:00Z") == "June 01, 2026"


def test_format_date_none():
    assert format_date(None) is None
    assert format_date("bad-date") is None


def test_format_tax_rate():
    assert format_tax_rate("0.0800") == "8%"
    assert format_tax_rate("0.1025") == "10.25%"
    assert format_tax_rate("0.0000") == "0%"
    assert format_tax_rate("bad") == "0%"


def test_format_quantity():
    assert format_quantity("2") == "2"
    assert format_quantity("2.00") == "2"
    assert format_quantity("4.50") == "4.5"
    assert format_quantity("1.250") == "1.25"


def test_build_pdf_view_model():
    vm = build_pdf_view_model(
        _fake_invoice(), _fake_client(), _fake_org(), _fake_line_items()
    )
    assert isinstance(vm, InvoicePdfViewModel)
    assert vm.invoice_number == "INV-0001"
    assert vm.invoice_status == "sent"
    assert vm.is_void is False
    assert vm.client_name == "Acme Corp"
    assert vm.org_name == "Freelio Studio"
    assert vm.total_formatted == "$1,080.00"
    assert vm.subtotal_formatted == "$1,000.00"
    assert vm.tax_formatted == "$80.00"
    assert vm.tax_rate_formatted == "8%"
    assert vm.due_date_formatted == "February 15, 2026"
    assert vm.notes == "Test invoice"
    assert len(vm.line_items) == 1
    assert isinstance(vm.line_items[0], LineItemViewModel)
    assert vm.line_items[0].description == "Design work"
    assert vm.line_items[0].quantity == "2"
    assert vm.line_items[0].amount_formatted == "$1,000.00"


def test_build_pdf_view_model_void():
    vm = build_pdf_view_model(
        _fake_invoice(), _fake_client(), _fake_org(), _fake_line_items(), is_void=True
    )
    assert vm.is_void is True
