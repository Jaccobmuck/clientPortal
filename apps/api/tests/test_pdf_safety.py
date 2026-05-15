import pytest

from app.pdf.safety import PdfSafetyError, is_void_invoice, validate_pdf_status


@pytest.mark.parametrize("status", ["sent", "locked", "paid", "disputed", "resolved"])
def test_validate_allows_renderable(status):
    validate_pdf_status(status)


def test_validate_allows_void():
    validate_pdf_status("void")


def test_validate_rejects_draft():
    with pytest.raises(PdfSafetyError) as exc_info:
        validate_pdf_status("draft")
    assert exc_info.value.permanent is True


def test_validate_rejects_unknown():
    with pytest.raises(PdfSafetyError):
        validate_pdf_status("nonexistent")


def test_is_void_true():
    assert is_void_invoice("void") is True
    assert is_void_invoice("VOID") is True


def test_is_void_false():
    assert is_void_invoice("sent") is False
    assert is_void_invoice("paid") is False
    assert is_void_invoice("draft") is False
