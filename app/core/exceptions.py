"""Stable error codes carried by the unified HTTP error envelope."""

from __future__ import annotations


class AppException(Exception):
    """Business error with a machine-readable code and HTTP status."""

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str, details: object = None) -> None:
        """Keep the human message and optional structured details."""
        self.message = message
        self.details = details
        super().__init__(message)


class ValidationError(AppException):
    """Request payload failed semantic validation."""

    code = "validation_error"
    status_code = 422


class AuthError(AppException):
    """Missing or invalid credentials."""

    code = "unauthorized"
    status_code = 401


class ForbiddenError(AppException):
    """Authenticated but not allowed to act."""

    code = "forbidden"
    status_code = 403


class NotFoundError(AppException):
    """Requested resource does not exist."""

    code = "not_found"
    status_code = 404


class ConflictError(AppException):
    """Request conflicts with current state."""

    code = "conflict"
    status_code = 409


class RuntimeInitializationError(AppException):
    """Application bootstrap failed or another instance holds the database."""

    code = "runtime_initialization_error"
    status_code = 503
