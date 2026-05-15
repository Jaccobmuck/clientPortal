from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from app.pdf.viewmodel import InvoicePdfViewModel

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_invoice_html(vm: InvoicePdfViewModel) -> str:
    template = _env.get_template("invoice.html")
    return template.render(**asdict(vm))
