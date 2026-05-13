from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from postgrest import AsyncPostgrestClient

from app.exceptions import NotFoundError
from app.repositories import invoices as invoice_repo
from app.schemas.invoices import InvoiceStatus
from app.services import pay_tokens as pay_token_service

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeQuery:
    def __init__(self, db: FakeSupabaseClient, table: str) -> None:
        self._db = db
        self._table = table
        self._filters: list[tuple[str, str]] = []
        self._limit: int | None = None
        self._order: tuple[str, bool] | None = None
        self._update_payload: dict[str, Any] | None = None

    def select(self, *_args: object, **_kwargs: object) -> FakeQuery:
        return self

    def eq(self, column: str, value: object) -> FakeQuery:
        self._filters.append((column, str(value)))
        return self

    def limit(self, value: int) -> FakeQuery:
        self._limit = value
        return self

    def order(self, column: str, *, desc: bool = False) -> FakeQuery:
        self._order = (column, desc)
        return self

    def update(self, payload: dict[str, Any]) -> FakeQuery:
        self._update_payload = payload
        return self

    async def execute(self) -> FakeResponse:
        rows = [
            row
            for row in self._db.tables[self._table]
            if all(str(row.get(column)) == value for column, value in self._filters)
        ]

        if self._update_payload is not None:
            for row in rows:
                row.update(self._update_payload)

        if self._order is not None:
            column, desc = self._order
            rows = sorted(rows, key=lambda row: row[column], reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]

        return FakeResponse([row.copy() for row in rows])


class FakeSupabaseClient:
    def __init__(self, invoice_rows: list[dict[str, Any]]) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "invoices": invoice_rows,
            "invoice_line_items": [
                _line_item_row(UUID(str(row["id"]))) for row in invoice_rows
            ],
        }

    def from_(self, table: str) -> FakeQuery:
        return FakeQuery(self, table)


def _invoice_row(
    *,
    invoice_id: UUID,
    org_id: UUID,
    client_id: UUID,
    pay_token: UUID,
    status: InvoiceStatus,
) -> dict[str, Any]:
    now = datetime(2026, 5, 13, tzinfo=UTC).isoformat()
    return {
        "id": str(invoice_id),
        "org_id": str(org_id),
        "client_id": str(client_id),
        "project_id": None,
        "invoice_number": "INV-0001",
        "status": status.value,
        "pay_token": str(pay_token),
        "due_date": None,
        "issued_at": None,
        "sent_at": None,
        "paid_at": None,
        "voided_at": None,
        "locked": status != InvoiceStatus.DRAFT,
        "subtotal": "100.00",
        "tax_rate": "0",
        "tax_amount": "0.00",
        "total": "100.00",
        "notes": None,
        "created_at": now,
        "updated_at": now,
    }


def _line_item_row(invoice_id: UUID) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "invoice_id": str(invoice_id),
        "description": "Consulting",
        "quantity": "1",
        "unit_price": "100.00",
        "amount": "100.00",
        "sort_order": 0,
    }


def _db_with_invoice(status: InvoiceStatus) -> tuple[FakeSupabaseClient, dict[str, UUID]]:
    ids = {
        "invoice_id": uuid4(),
        "org_id": uuid4(),
        "client_id": uuid4(),
        "pay_token": uuid4(),
    }
    db = FakeSupabaseClient(
        [
            _invoice_row(
                invoice_id=ids["invoice_id"],
                org_id=ids["org_id"],
                client_id=ids["client_id"],
                pay_token=ids["pay_token"],
                status=status,
            )
        ]
    )
    return db, ids


def _as_supabase(db: FakeSupabaseClient) -> AsyncPostgrestClient:
    return cast(AsyncPostgrestClient, db)


async def test_lookup_valid_sent_invoice_by_token_succeeds() -> None:
    db, ids = _db_with_invoice(InvoiceStatus.SENT)

    invoice = await pay_token_service.lookup_public_invoice_by_token(
        _as_supabase(db), raw_token=str(ids["pay_token"])
    )

    assert invoice.id == ids["invoice_id"]
    assert invoice.status == InvoiceStatus.SENT
    assert invoice.line_items[0].description == "Consulting"


@pytest.mark.parametrize("status", [InvoiceStatus.DRAFT, InvoiceStatus.VOID])
async def test_lookup_private_invoice_by_token_fails_with_generic_not_found(
    status: InvoiceStatus,
) -> None:
    db, ids = _db_with_invoice(status)

    with pytest.raises(NotFoundError) as exc_info:
        await pay_token_service.lookup_public_invoice_by_token(
            _as_supabase(db), raw_token=str(ids["pay_token"])
        )

    assert exc_info.value.message == "invoice not found"
    assert exc_info.value.code == "invoice_not_found"


@pytest.mark.parametrize("raw_token", ["not-a-token", None])
async def test_lookup_invalid_or_missing_token_fails_with_generic_not_found(
    raw_token: object,
) -> None:
    db, _ids = _db_with_invoice(InvoiceStatus.SENT)

    with pytest.raises(NotFoundError) as exc_info:
        await pay_token_service.lookup_public_invoice_by_token(
            _as_supabase(db), raw_token=raw_token
        )

    assert exc_info.value.message == "invoice not found"
    assert exc_info.value.code == "invoice_not_found"


async def test_rotate_token_changes_token() -> None:
    db, ids = _db_with_invoice(InvoiceStatus.SENT)
    old_token = ids["pay_token"]

    new_token = await pay_token_service.rotate_invoice_pay_token(
        _as_supabase(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
    )

    assert new_token != old_token
    assert UUID(db.tables["invoices"][0]["pay_token"]) == new_token


async def test_rotate_token_with_wrong_org_fails_without_changing_token() -> None:
    db, ids = _db_with_invoice(InvoiceStatus.SENT)
    old_token = ids["pay_token"]

    with pytest.raises(NotFoundError):
        await pay_token_service.rotate_invoice_pay_token(
            _as_supabase(db),
            org_id=uuid4(),
            invoice_id=ids["invoice_id"],
        )

    assert UUID(db.tables["invoices"][0]["pay_token"]) == old_token


async def test_old_token_no_longer_finds_invoice_after_rotation() -> None:
    db, ids = _db_with_invoice(InvoiceStatus.SENT)
    old_token = ids["pay_token"]

    new_token = await pay_token_service.rotate_invoice_pay_token(
        _as_supabase(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
    )

    with pytest.raises(NotFoundError):
        await pay_token_service.lookup_public_invoice_by_token(
            _as_supabase(db), raw_token=str(old_token)
        )

    invoice = await pay_token_service.lookup_public_invoice_by_token(
        _as_supabase(db), raw_token=str(new_token)
    )
    assert invoice.id == ids["invoice_id"]


async def test_invalidation_rotates_token_when_pay_token_is_not_nullable() -> None:
    db, ids = _db_with_invoice(InvoiceStatus.SENT)
    old_token = ids["pay_token"]

    new_token = await pay_token_service.invalidate_invoice_pay_token(
        _as_supabase(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
    )

    assert not invoice_repo.PAY_TOKEN_NULLABLE
    assert new_token != old_token
    assert UUID(db.tables["invoices"][0]["pay_token"]) == new_token
