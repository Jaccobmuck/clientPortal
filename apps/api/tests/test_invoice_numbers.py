import pytest

from app.utils.invoice_numbers import format_invoice_number, sanitize_invoice_prefix


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Acme Design Studio", "ACME"),
        ("ACME LLC", "ACME"),
        ("Bob's Web Co.", "BOBS"),
        (" north-star studio ", "NORTH"),
        ("", "ORG"),
        ("!!!", "ORG"),
    ],
)
def test_sanitize_invoice_prefix(value: str, expected: str) -> None:
    assert sanitize_invoice_prefix(value) == expected


@pytest.mark.parametrize(
    ("prefix", "year", "sequence", "expected"),
    [
        ("ACME", 2026, 42, "ACME-2026-0042"),
        ("acme design studio", 2026, 1, "ACME-2026-0001"),
        ("ACME", 2026, 10000, "ACME-2026-10000"),
    ],
)
def test_format_invoice_number(
    prefix: str,
    year: int,
    sequence: int,
    expected: str,
) -> None:
    assert format_invoice_number(prefix, year, sequence) == expected


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_format_invoice_number_rejects_invalid_sequence(sequence: int) -> None:
    with pytest.raises(ValueError, match="sequence"):
        format_invoice_number("ACME", 2026, sequence)


@pytest.mark.parametrize("year", [0, 999, 10000, -2026, True])
def test_format_invoice_number_rejects_invalid_year(year: int) -> None:
    with pytest.raises(ValueError, match="year"):
        format_invoice_number("ACME", year, 1)
