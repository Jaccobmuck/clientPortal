from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.supabase import get_supabase
from app.pdf.data_loader import load_pdf_data
from app.pdf.renderer import render_pdf
from app.pdf.safety import PdfSafetyError, is_void_invoice, validate_pdf_status
from app.pdf.storage import ensure_invoice_bucket, upload_invoice_pdf
from app.pdf.template_renderer import render_invoice_html
from app.pdf.viewmodel import build_pdf_view_model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/pdf", tags=["internal"])


class PdfRenderRequest(BaseModel):
    invoice_id: str
    org_id: str


class PdfRenderResponse(BaseModel):
    success: bool
    storage_path: str | None = None
    file_size: int | None = None
    error: str | None = None
    permanent: bool = False


@router.post("/render", response_model=PdfRenderResponse)
async def render_invoice_pdf(request: PdfRenderRequest) -> PdfRenderResponse:
    supabase = await get_supabase()

    try:
        invoice, client, org, line_items = await load_pdf_data(
            supabase, request.invoice_id, request.org_id
        )
    except ValueError as exc:
        return PdfRenderResponse(success=False, error=str(exc), permanent=True)

    try:
        validate_pdf_status(invoice["status"])
    except PdfSafetyError as exc:
        return PdfRenderResponse(success=False, error=str(exc), permanent=exc.permanent)

    void = is_void_invoice(invoice["status"])
    vm = build_pdf_view_model(invoice, client, org, line_items, is_void=void)

    html = render_invoice_html(vm)
    pdf_bytes = render_pdf(html)

    await ensure_invoice_bucket(supabase)
    storage_path, file_size = await upload_invoice_pdf(
        supabase,
        org_id=request.org_id,
        invoice_id=request.invoice_id,
        pdf_bytes=pdf_bytes,
    )

    logger.info(
        "PDF rendered: invoice=%s path=%s size=%d",
        request.invoice_id,
        storage_path,
        file_size,
    )

    return PdfRenderResponse(
        success=True,
        storage_path=storage_path,
        file_size=file_size,
    )
