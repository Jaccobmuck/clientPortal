from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import AsyncClient

logger = logging.getLogger(__name__)

INVOICE_BUCKET = "invoices"


def build_storage_path(org_id: str, invoice_id: str) -> str:
    return f"orgs/{org_id}/invoices/{invoice_id}/invoice.pdf"


async def ensure_invoice_bucket(supabase: AsyncClient) -> None:
    try:
        await supabase.storage.get_bucket(INVOICE_BUCKET)
    except Exception:
        await supabase.storage.create_bucket(
            INVOICE_BUCKET,
            options={"public": False},
        )
        logger.info("Created storage bucket: %s", INVOICE_BUCKET)


async def upload_invoice_pdf(
    supabase: AsyncClient,
    *,
    org_id: str,
    invoice_id: str,
    pdf_bytes: bytes,
) -> tuple[str, int]:
    storage_path = build_storage_path(org_id, invoice_id)

    bucket = supabase.storage.from_(INVOICE_BUCKET)
    await bucket.upload(
        storage_path,
        pdf_bytes,
        {"content-type": "application/pdf", "upsert": "true"},
    )

    return storage_path, len(pdf_bytes)
