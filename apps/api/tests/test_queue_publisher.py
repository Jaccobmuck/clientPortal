from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from app.exceptions import InternalError
from app.utils.queues import (
    INVOICE_QUEUES,
    QUEUE_EMAIL,
    QUEUE_PDF,
    QUEUE_REMINDER,
    SCHEMA_VERSION,
    build_job_id,
    build_job_payload,
    ensure_invoice_jobs,
    ensure_job,
)

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ── Fake Supabase client with INSERT + JSON-path filtering ───────────────────


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeQuery:
    def __init__(self, db: FakeOutboxClient, table: str) -> None:
        self._db = db
        self._table = table
        self._filters: list[tuple[str, str]] = []
        self._limit: int | None = None
        self._insert_payload: dict[str, Any] | None = None

    def select(self, *_args: object, **_kwargs: object) -> FakeQuery:
        return self

    def eq(self, column: str, value: object) -> FakeQuery:
        self._filters.append((column, str(value)))
        return self

    def limit(self, value: int) -> FakeQuery:
        self._limit = value
        return self

    def insert(self, payload: dict[str, Any]) -> FakeQuery:
        self._insert_payload = payload
        return self

    def _match_row(self, row: dict[str, Any]) -> bool:
        for column, value in self._filters:
            if "->>" in column:
                col, key = column.split("->>")
                cell = row.get(col)
                if not isinstance(cell, dict) or str(cell.get(key)) != value:
                    return False
            elif str(row.get(column)) != value:
                return False
        return True

    async def execute(self) -> FakeResponse:
        if self._db.should_raise:
            raise APIError({"message": "fake error", "code": "500", "details": "", "hint": ""})

        if self._insert_payload is not None:
            row = {"id": str(uuid4()), **self._insert_payload}
            self._db.tables.setdefault(self._table, []).append(row)
            return FakeResponse([row])

        rows = [r for r in self._db.tables.get(self._table, []) if self._match_row(r)]
        if self._limit is not None:
            rows = rows[: self._limit]
        return FakeResponse([r.copy() for r in rows])


class FakeOutboxClient:
    def __init__(
        self,
        outbox_rows: list[dict[str, Any]] | None = None,
        *,
        should_raise: bool = False,
    ) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "job_outbox": list(outbox_rows or []),
        }
        self.should_raise = should_raise

    def from_(self, table: str) -> FakeQuery:
        return FakeQuery(self, table)


def _as_client(db: FakeOutboxClient) -> AsyncPostgrestClient:
    return cast("AsyncPostgrestClient", db)


# ── Helpers ──────────────────────────────────────────────────────────────────

_IDS = {
    "invoice_id": uuid4(),
    "org_id": uuid4(),
    "user_id": uuid4(),
    "send_event_id": uuid4(),
}


def _make_outbox_row(queue_name: str, status: str = "pending") -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "org_id": str(_IDS["org_id"]),
        "queue_name": queue_name,
        "payload": build_job_payload(
            invoice_id=_IDS["invoice_id"],
            org_id=_IDS["org_id"],
            user_id=_IDS["user_id"],
            send_event_id=_IDS["send_event_id"],
            queue_name=queue_name,
        ),
        "status": status,
        "created_at": "2026-05-13T00:00:00Z",
    }


# ── Pure function tests ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("queue_name", "expected_type"),
    [
        (QUEUE_PDF, "pdf"),
        (QUEUE_EMAIL, "initial-email"),
        (QUEUE_REMINDER, "reminders"),
    ],
)
def test_build_job_id_format(queue_name: str, expected_type: str) -> None:
    inv_id = uuid4()
    job_id = build_job_id(inv_id, queue_name)
    assert job_id == f"invoice:{inv_id}:{expected_type}:v{SCHEMA_VERSION}"


def test_build_job_payload_required_fields() -> None:
    payload = build_job_payload(
        invoice_id=_IDS["invoice_id"],
        org_id=_IDS["org_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
        queue_name=QUEUE_PDF,
    )
    assert payload["invoice_id"] == str(_IDS["invoice_id"])
    assert payload["org_id"] == str(_IDS["org_id"])
    assert payload["requested_by_user_id"] == str(_IDS["user_id"])
    assert payload["send_event_id"] == str(_IDS["send_event_id"])
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "job_id" in payload


def test_build_job_payload_excludes_sensitive_fields() -> None:
    payload = build_job_payload(
        invoice_id=_IDS["invoice_id"],
        org_id=_IDS["org_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
        queue_name=QUEUE_PDF,
    )
    assert "pay_token" not in payload
    assert "pay_url" not in payload


# ── ensure_job tests ─────────────────────────────────────────────────────────


async def test_ensure_job_creates_new_job_when_empty() -> None:
    db = FakeOutboxClient()
    payload = build_job_payload(
        invoice_id=_IDS["invoice_id"],
        org_id=_IDS["org_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
        queue_name=QUEUE_PDF,
    )

    status = await ensure_job(
        _as_client(db), org_id=_IDS["org_id"], queue_name=QUEUE_PDF, payload=payload,
    )

    assert status == "queued"
    assert len(db.tables["job_outbox"]) == 1
    assert db.tables["job_outbox"][0]["queue_name"] == QUEUE_PDF


async def test_ensure_job_returns_existing_when_already_present() -> None:
    existing_row = _make_outbox_row(QUEUE_PDF, status="pending")
    db = FakeOutboxClient(outbox_rows=[existing_row])

    payload = build_job_payload(
        invoice_id=_IDS["invoice_id"],
        org_id=_IDS["org_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
        queue_name=QUEUE_PDF,
    )

    status = await ensure_job(
        _as_client(db), org_id=_IDS["org_id"], queue_name=QUEUE_PDF, payload=payload,
    )

    assert status == "pending"
    assert len(db.tables["job_outbox"]) == 1


async def test_ensure_job_raises_internal_error_on_api_failure() -> None:
    db = FakeOutboxClient(should_raise=True)
    payload = build_job_payload(
        invoice_id=_IDS["invoice_id"],
        org_id=_IDS["org_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
        queue_name=QUEUE_PDF,
    )

    with pytest.raises(InternalError):
        await ensure_job(
            _as_client(db), org_id=_IDS["org_id"], queue_name=QUEUE_PDF, payload=payload,
        )


# ── ensure_invoice_jobs tests ────────────────────────────────────────────────


async def test_ensure_invoice_jobs_creates_all_three() -> None:
    db = FakeOutboxClient()

    statuses = await ensure_invoice_jobs(
        _as_client(db),
        org_id=_IDS["org_id"],
        invoice_id=_IDS["invoice_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
    )

    assert len(db.tables["job_outbox"]) == 3
    queues_created = {r["queue_name"] for r in db.tables["job_outbox"]}
    assert queues_created == {QUEUE_PDF, QUEUE_EMAIL, QUEUE_REMINDER}
    assert statuses == {"pdf": "queued", "email": "queued", "reminders": "queued"}


async def test_ensure_invoice_jobs_repairs_missing_only() -> None:
    existing_pdf = _make_outbox_row(QUEUE_PDF, status="pending")
    db = FakeOutboxClient(outbox_rows=[existing_pdf])

    statuses = await ensure_invoice_jobs(
        _as_client(db),
        org_id=_IDS["org_id"],
        invoice_id=_IDS["invoice_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
    )

    assert len(db.tables["job_outbox"]) == 3
    assert statuses["pdf"] == "pending"
    assert statuses["email"] == "queued"
    assert statuses["reminders"] == "queued"


async def test_ensure_invoice_jobs_noop_when_all_exist() -> None:
    rows = [
        _make_outbox_row(QUEUE_PDF, status="pending"),
        _make_outbox_row(QUEUE_EMAIL, status="pending"),
        _make_outbox_row(QUEUE_REMINDER, status="pending"),
    ]
    db = FakeOutboxClient(outbox_rows=rows)

    statuses = await ensure_invoice_jobs(
        _as_client(db),
        org_id=_IDS["org_id"],
        invoice_id=_IDS["invoice_id"],
        user_id=_IDS["user_id"],
        send_event_id=_IDS["send_event_id"],
    )

    assert len(db.tables["job_outbox"]) == 3
    assert all(s == "pending" for s in statuses.values())


async def test_deterministic_job_ids_consistent_across_calls() -> None:
    db = FakeOutboxClient()
    kwargs = {
        "org_id": _IDS["org_id"],
        "invoice_id": _IDS["invoice_id"],
        "user_id": _IDS["user_id"],
        "send_event_id": _IDS["send_event_id"],
    }

    await ensure_invoice_jobs(_as_client(db), **kwargs)
    first_ids = {r["payload"]["job_id"] for r in db.tables["job_outbox"]}

    second_ids = set()
    for queue_name in INVOICE_QUEUES:
        second_ids.add(build_job_id(_IDS["invoice_id"], queue_name))

    assert first_ids == second_ids
