from fastapi import FastAPI

from app.core.exceptions import InvoiceStatusError
from app.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
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


def test_app_exception_defaults() -> None:
    err = AppException()
    assert err.message == "Internal server error"
    assert err.code == "internal_error"
    assert err.field is None


def test_app_exception_custom_message() -> None:
    err = AppException("something went wrong")
    assert err.message == "something went wrong"


def test_app_exception_custom_code_and_field() -> None:
    err = AppException("bad value", code="bad_value", field="amount")
    assert err.code == "bad_value"
    assert err.field == "amount"


def test_not_found_error() -> None:
    err = NotFoundError()
    assert err.code == "not_found"
    assert err.message == "Resource not found"


def test_forbidden_error() -> None:
    err = ForbiddenError()
    assert err.code == "forbidden"


def test_conflict_error() -> None:
    err = ConflictError()
    assert err.code == "conflict"


def test_validation_error() -> None:
    err = ValidationError()
    assert err.code == "validation_error"


def test_unauthorized_error() -> None:
    err = UnauthorizedError()
    assert err.code == "unauthorized"


def test_invoice_status_error() -> None:
    err = InvoiceStatusError()
    assert err.code == "invoice_status_error"
    assert err.message == "Invalid invoice status transition"


def test_invoice_status_error_inherits_conflict() -> None:
    assert issubclass(InvoiceStatusError, ConflictError)


def test_error_is_exception() -> None:
    assert issubclass(AppException, Exception)
    assert issubclass(NotFoundError, AppException)
