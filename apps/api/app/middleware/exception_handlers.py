import logging
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.schemas.base import BaseResponse, ErrorDetail

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[type[AppException], int] = {
    NotFoundError: 404,
    ValidationError: 422,
    ConflictError: 409,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    InternalError: 500,
    AppException: 500,
}


def _get_request_id(request: Request) -> str:
    try:
        return request.state.request_id  # type: ignore[no-any-return]
    except AttributeError:
        return str(uuid.uuid4())


def _get_status_code(exc: AppException) -> int:
    for cls in type(exc).__mro__:
        if cls in _STATUS_MAP:
            return _STATUS_MAP[cls]
    return 500


def _error_response(status_code: int, error: ErrorDetail, request_id: str) -> JSONResponse:
    body = BaseResponse[None](
        success=False,
        data=None,
        error=error,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )


async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    request_id = _get_request_id(request)
    status_code = _get_status_code(exc)
    error = ErrorDetail(code=exc.code, message=exc.message, field=exc.field)
    return _error_response(status_code, error, request_id)


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _get_request_id(request)
    first = exc.errors()[0] if exc.errors() else {}
    field = " -> ".join(str(loc) for loc in first.get("loc", []))
    error = ErrorDetail(
        code="validation_error",
        message=first.get("msg", "Validation error"),
        field=field or None,
    )
    return _error_response(422, error, request_id)


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = _get_request_id(request)
    error = ErrorDetail(
        code="http_error",
        message=str(exc.detail),
    )
    return _error_response(exc.status_code, error, request_id)


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.error(
        "Unhandled exception [request_id=%s]:\n%s",
        request_id,
        traceback.format_exc(),
    )
    error = ErrorDetail(
        code="internal_error",
        message="Internal server error",
    )
    return _error_response(500, error, request_id)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, _handle_app_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled_exception)
