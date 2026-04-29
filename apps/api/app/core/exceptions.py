"""
Global exception handlers. Routes raise; these translate to HTTP responses.
Never put try/except in route handlers — raise domain exceptions instead.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base domain exception."""
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Forbidden"


class ConflictError(AppError):
    status_code = 409
    detail = "Conflict"


class UnprocessableError(AppError):
    status_code = 422
    detail = "Unprocessable entity"


class InvoiceStatusError(AppError):
    """Raised when a status transition is illegal."""
    status_code = 409
    detail = "Invalid invoice status transition"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_req: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_req: Request, exc: Exception) -> JSONResponse:
        # P17 will add Sentry capture here
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
