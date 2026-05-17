from typing import Any

from supabase import AsyncClient

from app.core.settings import settings
from app.exceptions import InternalError


class PdfStorageService:
    def __init__(self, supabase: AsyncClient, *, bucket: str | None = None) -> None:
        self._supabase = supabase
        self._bucket = bucket or settings.INVOICE_PDF_BUCKET

    async def create_signed_invoice_pdf_url(
        self,
        storage_path: str,
        *,
        expires_in_seconds: int = 600,
    ) -> str:
        result: Any = await self._supabase.storage.from_(self._bucket).create_signed_url(
            storage_path,
            expires_in_seconds,
        )
        if isinstance(result, dict):
            url = result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")
        else:
            url = getattr(result, "signed_url", None) or getattr(result, "signedURL", None)
        if not isinstance(url, str) or not url:
            raise InternalError("failed to create signed invoice PDF URL")
        return url
