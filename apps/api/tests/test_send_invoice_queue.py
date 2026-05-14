from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from app.schemas.invoices import InvoiceStatus
from app.services import invoices as invoice_service
from app.utils.queues import QUEUE_EMAIL, QUEUE_PDF, QUEUE_REMINDER, build_job_id

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ── Fake Supabase client ─────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeQuery:
    def __init__(self, db: FakeSendClient, table: str) -> None:
        self._db = db
        self._table = table
        self._filters: list[tuple[str, str]] = []
        self._limit: int | None = None
        self._insert_payload: dict[str, Any] | None = None
        self._update_payload: dict[str, Any] | None = None

    def select(self, *_args: object, **_kwargs: object) -> FakeQuery:
        return self

    def eq(self, column: str, value: object) -> FakeQuery:
        self._filters.append((column, str(value)))
        return self

    def limit(self, value: int) -> FakeQuery:
        self._limit = value
        return self

    def order(self, _column: str, *, desc: bool = False) -> FakeQuery:
        return self

    def is_(self, column: str, value: str) -> FakeQuery:
        if value == "null":
            self._filters.append((f"__is_null__{column}", "true"))
        return self

    def insert(self, payload: dict[str, Any]) -> FakeQuery:
        self._insert_payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> FakeQuery:
        self._update_payload = payload
        return self

    def _match_row(self, row: dict[str, Any]) -> bool:
        for column, value in self._filters:
            if column.startswith("__is_null__"):
                real_col = column.removeprefix("__is_null__")
                if row.get(real_col) is not None:
                    return False
            elif "->>" in column:
                col, key = column.split("->>")
                cell = row.get(col)
                if not isinstance(cell, dict) or str(cell.get(key)) != value:
                    return False
            elif str(row.get(column)) != value:
                return False
        return True

    async def execute(self) -> FakeResponse:
        if self._insert_payload is not None:
            row = {"id": str(uuid4()), **self._insert_payload}
            self._db.tables.setdefault(self._table, []).append(row)
            return FakeResponse([row])

        rows = [r for r in self._db.tables.get(self._table, []) if self._match_row(r)]

        if self._update_payload is not None:
            for row in rows:
                row.update(self._update_payload)

        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResponse([r.copy() for r in rows])


class FakeSendClient:
    def __init__(
        self,
        invoices: list[dict[str, Any]],
        clients: list[dict[str, Any]] | None = None,
        outbox: list[dict[str, Any]] | None = None,
    ) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "invoices": invoices,
            "invoice_line_items": [_line_item_row(UUID(str(inv["id"]))) for inv in invoices],
            "clients": list(clients or []),
            "job_outbox": list(outbox or []),
        }

    def from_(self, table: str) -> FakeQuery:
        return FakeQuery(self, table)


def _as_client(db: FakeSendClient) -> AsyncPostgrestClient:
    return cast("AsyncPostgrestClient", db)


# ── Test data factories ──────────────────────────────────────────────────────

_NOW = datetime(2026, 5, 13, tzinfo=UTC).isoformat()


def _invoice_row(
    *,
    invoice_id: UUID,
    org_id: UUID,
    client_id: UUID,
    status: InvoiceStatus = InvoiceStatus.DRAFT,
) -> dict[str, Any]:
    return {
        "id": str(invoice_id),
        "org_id": str(org_id),
        "client_id": str(client_id),
        "project_id": None,
        "invoice_number": "INV-0001",
        "status": status.value,
        "pay_token": str(uuid4()),
        "due_date": None,
        "issued_at": None,
        "sent_at": None if status == InvoiceStatus.DRAFT else _NOW,
        "paid_at": None,
        "voided_at": None,
        "locked": status != InvoiceStatus.DRAFT,
        "subtotal": "100.00",
        "tax_rate": "0",
        "tax_amount": "0.00",
        "total": "100.00",
        "notes": None,
        "created_at": _NOW,
        "updated_at": _NOW,
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


def _client_row(*, client_id: UUID, org_id: UUID) -> dict[str, Any]:
    return {
        "id": str(client_id),
        "org_id": str(org_id),
        "name": "Test Client",
        "email": "test@example.com",
        "phone": None,
        "company": None,
        "notes": None,
        "deleted_at": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _setup_draft() -> tuple[FakeSendClient, dict[str, UUID]]:
    ids = {
        "invoice_id": uuid4(),
        "org_id": uuid4(),
        "client_id": uuid4(),
        "user_id": uuid4(),
    }
    inv = _invoice_row(
        invoice_id=ids["invoice_id"],
        org_id=ids["org_id"],
        client_id=ids["client_id"],
    )
    client = _client_row(client_id=ids["client_id"], org_id=ids["org_id"])
    db = FakeSendClient(invoices=[inv], clients=[client])
    return db, ids


def _setup_sent(
    outbox_queues: list[str] | None = None,
) -> tuple[FakeSendClient, dict[str, UUID]]:
    ids = {
        "invoice_id": uuid4(),
        "org_id": uuid4(),
        "client_id": uuid4(),
        "user_id": uuid4(),
    }
    inv = _invoice_row(
        invoice_id=ids["invoice_id"],
        org_id=ids["org_id"],
        client_id=ids["client_id"],
        status=InvoiceStatus.SENT,
    )
    client = _client_row(client_id=ids["client_id"], org_id=ids["org_id"])

    outbox: list[dict[str, Any]] = []
    if outbox_queues:
        from app.utils.queues import build_job_payload

        for q in outbox_queues:
            outbox.append(
                {
                    "id": str(uuid4()),
                    "org_id": str(ids["org_id"]),
                    "queue_name": q,
                    "payload": build_job_payload(
                        invoice_id=ids["invoice_id"],
                        org_id=ids["org_id"],
                        user_id=ids["user_id"],
                        send_event_id=uuid4(),
                        queue_name=q,
                    ),
                    "status": "pending",
                    "created_at": _NOW,
                }
            )

    db = FakeSendClient(invoices=[inv], clients=[client], outbox=outbox)
    return db, ids


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_draft_send_enqueues_all_three_jobs() -> None:
    db, ids = _setup_draft()

    result = await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    assert result.status == InvoiceStatus.SENT
    assert result.queue_status.pdf == "queued"
    assert result.queue_status.email == "queued"
    assert result.queue_status.reminders == "queued"
    assert len(db.tables["job_outbox"]) == 3

    queues = {r["queue_name"] for r in db.tables["job_outbox"]}
    assert queues == {QUEUE_PDF, QUEUE_EMAIL, QUEUE_REMINDER}


async def test_draft_send_includes_send_event_id() -> None:
    db, ids = _setup_draft()

    result = await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    assert result.send_event_id is not None
    for row in db.tables["job_outbox"]:
        assert row["payload"]["send_event_id"] == str(result.send_event_id)


async def test_draft_send_payloads_contain_user_id() -> None:
    db, ids = _setup_draft()

    await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    for row in db.tables["job_outbox"]:
        assert row["payload"]["requested_by_user_id"] == str(ids["user_id"])


async def test_draft_send_payloads_exclude_sensitive_fields() -> None:
    db, ids = _setup_draft()

    await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    for row in db.tables["job_outbox"]:
        assert "pay_token" not in row["payload"]
        assert "pay_url" not in row["payload"]


async def test_draft_send_uses_deterministic_job_ids() -> None:
    db, ids = _setup_draft()

    await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    actual_ids = {r["payload"]["job_id"] for r in db.tables["job_outbox"]}
    expected_ids = {
        build_job_id(ids["invoice_id"], q) for q in [QUEUE_PDF, QUEUE_EMAIL, QUEUE_REMINDER]
    }
    assert actual_ids == expected_ids


async def test_already_sent_repairs_missing_jobs() -> None:
    db, ids = _setup_sent(outbox_queues=[QUEUE_PDF])

    result = await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    assert result.status == InvoiceStatus.SENT
    assert result.queue_status.pdf == "pending"
    assert result.queue_status.email == "queued"
    assert result.queue_status.reminders == "queued"
    assert len(db.tables["job_outbox"]) == 3


async def test_already_sent_all_jobs_present_is_noop() -> None:
    db, ids = _setup_sent(outbox_queues=[QUEUE_PDF, QUEUE_EMAIL, QUEUE_REMINDER])
    initial_count = len(db.tables["job_outbox"])

    result = await invoice_service.send_invoice(
        _as_client(db),
        org_id=ids["org_id"],
        invoice_id=ids["invoice_id"],
        user_id=ids["user_id"],
    )

    assert result.status == InvoiceStatus.SENT
    assert len(db.tables["job_outbox"]) == initial_count


async def test_send_event_id_differs_between_calls() -> None:
    db1, ids1 = _setup_draft()
    db2, ids2 = _setup_draft()

    r1 = await invoice_service.send_invoice(
        _as_client(db1),
        org_id=ids1["org_id"],
        invoice_id=ids1["invoice_id"],
        user_id=ids1["user_id"],
    )
    r2 = await invoice_service.send_invoice(
        _as_client(db2),
        org_id=ids2["org_id"],
        invoice_id=ids2["invoice_id"],
        user_id=ids2["user_id"],
    )

    assert r1.send_event_id != r2.send_event_id
