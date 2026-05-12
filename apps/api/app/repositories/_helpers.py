from datetime import UTC, datetime
from decimal import Decimal


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def cents_to_db(cents: int) -> str:
    return str(Decimal(cents) / Decimal(100))


def db_to_cents(db_value: str | float | Decimal) -> int:
    return int(Decimal(str(db_value)) * Decimal(100))


def basis_points_to_db(bp: int) -> str:
    return str(Decimal(bp) / Decimal(10000))


def db_to_basis_points(db_value: str | float | Decimal) -> int:
    return int(Decimal(str(db_value)) * Decimal(10000))
