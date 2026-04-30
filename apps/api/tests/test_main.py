from fastapi import FastAPI

from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    InvoiceStatusError,
    NotFoundError,
    UnprocessableError,
)
from app.main import app, create_app


def test_create_app_returns_fastapi() -> None:
    result = create_app()
    assert isinstance(result, FastAPI)


def test_app_title() -> None:
    assert app.title == "InvoiceSaaS API"


def test_app_version() -> None:
    assert app.version == "0.1.0"


def test_app_docs_available_in_development() -> None:
    assert app.docs_url == "/docs"


def test_app_error_default_detail() -> None:
    err = AppError()
    assert err.detail == "Internal server error"
    assert err.status_code == 500


def test_app_error_custom_detail() -> None:
    err = AppError("something went wrong")
    assert err.detail == "something went wrong"


def test_not_found_error() -> None:
    err = NotFoundError()
    assert err.status_code == 404
    assert err.detail == "Resource not found"


def test_forbidden_error() -> None:
    err = ForbiddenError()
    assert err.status_code == 403


def test_conflict_error() -> None:
    err = ConflictError()
    assert err.status_code == 409


def test_unprocessable_error() -> None:
    err = UnprocessableError()
    assert err.status_code == 422


def test_invoice_status_error() -> None:
    err = InvoiceStatusError()
    assert err.status_code == 409
    assert err.detail == "Invalid invoice status transition"


def test_error_is_exception() -> None:
    assert issubclass(AppError, Exception)
    assert issubclass(NotFoundError, AppError)
