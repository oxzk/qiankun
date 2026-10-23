"""Translate every failure into the unified error envelope."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas.response import error_response
from app.core.exceptions import AppException


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers for the four failure classes."""

    @app.exception_handler(AppException)
    async def handle_app(_: Request, exc: AppException) -> Any:
        """Business errors carry their own status and code."""
        return _json(exc.status_code, error_response(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> Any:
        """Describe invalid fields without echoing submitted values."""
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return _json(422, error_response("validation_error", "Request validation failed", details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> Any:
        """Route-level rejections such as 404 keep the envelope."""
        return _json(exc.status_code, error_response("http_error", str(exc.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> Any:
        """Log the full stack, answer with a fixed message."""
        from loguru import logger

        logger.exception("Unhandled exception")
        return _json(500, error_response("internal_error", "Internal server error"))


def _json(status_code: int, payload: Any) -> Any:
    """Build a JSONResponse at import-safe call time."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
