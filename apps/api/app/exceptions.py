"""Application exception hierarchy.

No HTTP status codes here — status code mapping belongs exclusively
to the exception handler layer.
"""


class AppException(Exception):
    _default_message: str = "Internal server error"
    _default_code: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code or self._default_code
        self.message = message or self._default_message
        self.field = field
        super().__init__(self.message)


class NotFoundError(AppException):
    _default_message = "Resource not found"
    _default_code = "not_found"


class ValidationError(AppException):
    _default_message = "Validation error"
    _default_code = "validation_error"


class ConflictError(AppException):
    _default_message = "Resource conflict"
    _default_code = "conflict"


class UnauthorizedError(AppException):
    _default_message = "Authentication required"
    _default_code = "unauthorized"


class ForbiddenError(AppException):
    _default_message = "Forbidden"
    _default_code = "forbidden"


class InternalError(AppException):
    _default_message = "Internal server error"
    _default_code = "internal_error"


class SubscriptionRequiredError(AppException):
    _default_message = "upgrade to a paid plan to create additional organizations"
    _default_code = "subscription_required"
