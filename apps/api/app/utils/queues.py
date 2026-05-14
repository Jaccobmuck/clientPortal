"""Invoice queue publisher — outbox-based enqueue for BullMQ workers.

Workers must:
- Reload invoice/client/org from DB (do not trust stale payload).
- Skip draft or void invoices.
- Verify invoice is still client-viewable before emailing.
- Check invoice status before sending reminders.
- Never log raw pay tokens or full pay URLs.
- Use invoice_id + org_id as correlation IDs.
- Treat duplicate jobs (same job_id) as idempotent no-ops.

The real BullMQ bridge (outbox relay → Redis) is a P7 concern.
This module writes to the job_outbox Postgres table only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from postgrest.exceptions import APIError

from app.exceptions import InternalError

if TYPE_CHECKING:
    from uuid import UUID

    from postgrest import AsyncPostgrestClient

# ── Queue name constants (match workers/src/index.ts) ────────────────────────

QUEUE_PDF = "pdf-queue"
QUEUE_EMAIL = "email-queue"
QUEUE_REMINDER = "reminder-queue"

INVOICE_QUEUES = [QUEUE_PDF, QUEUE_EMAIL, QUEUE_REMINDER]

SCHEMA_VERSION = 1

_QUEUE_TYPE_MAP: dict[str, str] = {
    QUEUE_PDF: "pdf",
    QUEUE_EMAIL: "initial-email",
    QUEUE_REMINDER: "reminders",
}


# ── Pure builders ─────────────────────────────────────────────────────────────


def build_job_id(invoice_id: UUID, queue_name: str) -> str:
    queue_type = _QUEUE_TYPE_MAP[queue_name]
    return f"invoice:{invoice_id}:{queue_type}:v{SCHEMA_VERSION}"


def build_job_payload(
    *,
    invoice_id: UUID,
    org_id: UUID,
    user_id: UUID,
    send_event_id: UUID,
    queue_name: str,
) -> dict[str, Any]:
    """Small, ID-only payload — workers reload full data from the DB."""
    return {
        "job_id": build_job_id(invoice_id, queue_name),
        "invoice_id": str(invoice_id),
        "org_id": str(org_id),
        "requested_by_user_id": str(user_id),
        "send_event_id": str(send_event_id),
        "schema_version": SCHEMA_VERSION,
    }


# ── Idempotent outbox operations ─────────────────────────────────────────────


async def find_existing_job(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    queue_name: str,
    job_id: str,
) -> dict[str, Any] | None:
    try:
        response = (
            await client.from_("job_outbox")
            .select("id, queue_name, payload, status, created_at")
            .eq("org_id", str(org_id))
            .eq("queue_name", queue_name)
            .eq("payload->>job_id", job_id)
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows: list[dict[str, Any]] = response.data or []
    return rows[0] if rows else None


async def ensure_job(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    queue_name: str,
    payload: dict[str, Any],
) -> str:
    """Idempotently ensure a job exists in the outbox.

    Returns the outbox row status: ``"queued"`` for newly inserted jobs,
    or the existing ``status`` value if the job was already present.
    """
    job_id = payload["job_id"]
    existing = await find_existing_job(
        client, org_id=org_id, queue_name=queue_name, job_id=job_id,
    )
    if existing is not None:
        return existing["status"]

    try:
        await (
            client.from_("job_outbox")
            .insert(
                {
                    "org_id": str(org_id),
                    "queue_name": queue_name,
                    "payload": payload,
                }
            )
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    return "queued"


async def ensure_invoice_jobs(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    invoice_id: UUID,
    user_id: UUID,
    send_event_id: UUID,
) -> dict[str, str]:
    """Ensure pdf, email, and reminder jobs exist for an invoice send.

    Returns a mapping of ``{"pdf": status, "email": status, "reminders": status}``.
    """
    statuses: dict[str, str] = {}
    status_keys = {QUEUE_PDF: "pdf", QUEUE_EMAIL: "email", QUEUE_REMINDER: "reminders"}

    for queue_name in INVOICE_QUEUES:
        payload = build_job_payload(
            invoice_id=invoice_id,
            org_id=org_id,
            user_id=user_id,
            send_event_id=send_event_id,
            queue_name=queue_name,
        )
        status = await ensure_job(client, org_id=org_id, queue_name=queue_name, payload=payload)
        statuses[status_keys[queue_name]] = status

    return statuses
