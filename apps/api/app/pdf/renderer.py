from __future__ import annotations

import logging

logger = logging.getLogger("weasyprint")


def render_pdf(html: str) -> bytes:
    import weasyprint

    try:
        pdf_bytes: bytes = weasyprint.HTML(string=html).write_pdf()
    except Exception as exc:
        msg = f"WeasyPrint rendering failed: {exc}"
        raise RuntimeError(msg) from exc

    if not pdf_bytes:
        raise RuntimeError("WeasyPrint returned empty PDF bytes")

    return pdf_bytes
