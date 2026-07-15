"""Unified exception classes and handlers."""

from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_423_LOCKED,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_503_SERVICE_UNAVAILABLE,
)


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = HTTP_400_BAD_REQUEST,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class ValidationException(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_422_UNPROCESSABLE_ENTITY, details=details)


class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_401_UNAUTHORIZED, details=details)


class AuthorizationException(AppException):
    def __init__(self, message: str = "Access denied", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_403_FORBIDDEN, details=details)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_404_NOT_FOUND, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_409_CONFLICT, details=details)


class RateLimitException(AppException):
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_429_TOO_MANY_REQUESTS, details=details)


class AccountLockedException(AppException):
    def __init__(self, message: str = "Account is locked", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_423_LOCKED, details=details)


class EmailNotVerifiedException(AppException):
    def __init__(self, message: str = "Email not verified", user_id: str = None, details: Optional[Any] = None):
        # Include user_id in details so frontend can use it for verification endpoint
        exception_details = details or {}
        if user_id:
            exception_details["user_id"] = user_id
        super().__init__(message=message, status_code=HTTP_403_FORBIDDEN, details=exception_details)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service unavailable", details: Optional[Any] = None):
        super().__init__(message=message, status_code=HTTP_503_SERVICE_UNAVAILABLE, details=details)


# ── Response builder ──────────────────────────────────────────────────────────

def _build_response(status_code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "code": status_code,
            "data": data,
        },
    )


# ── Exception handlers ────────────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _build_response(exc.status_code, exc.message, exc.details)


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    return _build_response(exc.status_code, str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return _build_response(HTTP_422_UNPROCESSABLE_ENTITY, "Request validation failed", errors)
