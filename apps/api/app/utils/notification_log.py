from uuid import UUID

from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.exceptions import InternalError
from app.repositories._helpers import utc_now


async def write_audit(
    client: AsyncPostgrestClient,
    *,
    invoice_id: UUID,
    event: str,
    note: str,
    org_id: UUID,
    user_id: UUID,
) -> None:
    try:
        await (
            client.from_("notification_log")
            .insert(
                {
                    "org_id": str(org_id),
                    "invoice_id": str(invoice_id),
                    "type": event,
                    "payload": {"note": note, "user_id": str(user_id)},
                    "created_at": utc_now(),
                }
            )
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc
