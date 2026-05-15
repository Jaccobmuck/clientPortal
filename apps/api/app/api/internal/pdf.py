from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

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
    return PdfRenderResponse(
        success=False,
        error="PDF rendering not yet implemented",
        permanent=True,
    )
