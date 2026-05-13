import re

_DEFAULT_PREFIX = "ORG"
_MAX_PREFIX_LENGTH = 8
_MIN_YEAR = 1000
_MAX_YEAR = 9999


def sanitize_invoice_prefix(org_name_or_prefix: str) -> str:
    value = str(org_name_or_prefix).strip().upper()
    value = re.sub(r"[-_/]+", " ", value)
    value = re.sub(r"[^A-Z0-9\s]", "", value)
    words = [word for word in value.split() if word]

    if not words:
        return _DEFAULT_PREFIX

    return words[0][:_MAX_PREFIX_LENGTH] or _DEFAULT_PREFIX


def format_invoice_number(prefix: str, year: int, sequence: int) -> str:
    invoice_prefix = sanitize_invoice_prefix(prefix)
    invoice_year = _validate_year(year)
    invoice_sequence = _validate_sequence(sequence)

    return f"{invoice_prefix}-{invoice_year}-{invoice_sequence:04d}"


def _validate_year(year: int) -> int:
    if isinstance(year, bool):
        raise ValueError("year must be a four-digit integer")

    try:
        invoice_year = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError("year must be a four-digit integer") from exc

    if invoice_year < _MIN_YEAR or invoice_year > _MAX_YEAR:
        raise ValueError("year must be a four-digit integer")

    return invoice_year


def _validate_sequence(sequence: int) -> int:
    if isinstance(sequence, bool):
        raise ValueError("sequence must be a positive integer")

    try:
        invoice_sequence = int(sequence)
    except (TypeError, ValueError) as exc:
        raise ValueError("sequence must be a positive integer") from exc

    if invoice_sequence <= 0:
        raise ValueError("sequence must be a positive integer")

    return invoice_sequence
