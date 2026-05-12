from typing import Any
from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import InternalError


async def enqueue_pdf(client: AsyncPostgrestClient, *, invoice_id: UUID, org_id: UUID) -> None:
    await _enqueue(client, org_id=org_id, queue_name="pdf", payload={"invoice_id": str(invoice_id)})


async def enqueue_email(client: AsyncPostgrestClient, *, invoice_id: UUID, org_id: UUID) -> None:
    await _enqueue(
        client, org_id=org_id, queue_name="email", payload={"invoice_id": str(invoice_id)}
    )


async def _enqueue(
    client: AsyncPostgrestClient,
    *,
    org_id: UUID,
    queue_name: str,
    payload: dict[str, Any],
) -> None:
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
