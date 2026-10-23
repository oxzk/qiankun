"""Unified success and error envelopes for every endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class ResponseModel(BaseModel):
    """Shared serialization behaviour for all response models."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SuccessResponse[T](ResponseModel):
    """Wrap service return values so routers never build envelopes."""

    success: Literal[True] = True
    data: T

    @model_validator(mode="before")
    @classmethod
    def envelope(cls, value: Any) -> Any:
        """Accept raw service values and only pass through existing envelopes."""
        if isinstance(value, cls):
            return value
        return {"success": True, "data": value}


class ErrorModel(BaseModel):
    """Machine-readable description of a failure."""

    code: str
    message: str
    details: object = None


class ErrorResponse(BaseModel):
    """Uniform failure envelope produced only by exception handlers."""

    success: Literal[False] = False
    error: ErrorModel


def error_response(code: str, message: str, details: object = None) -> ErrorResponse:
    """Build the failure envelope in one place."""
    return ErrorResponse(error=ErrorModel(code=code, message=message, details=details))
