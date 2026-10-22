"""FastAPI 异常处理器。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import settings
from app.shared.errors import AppError
from app.shared.logger import logger
from app.schemas.responses import APIResponse


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        """处理应用业务异常。"""
        return error_response(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """处理请求参数校验异常。"""
        data = {"errors": format_validation_errors(exc)}
        return error_response(422, "请求参数无效", data=data)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """处理 HTTP 异常。"""
        message = str(exc.detail) if exc.detail else "请求失败"
        return error_response(exc.status_code, message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """处理未预期异常。"""
        logger.exception(
            "未处理异常: %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        data = None
        if settings.app_debug:
            data = {
                "type": exc.__class__.__name__,
                "detail": str(exc),
            }
        return error_response(500, unexpected_error_message(exc), data=data)


def error_response(
    status_code: int,
    message: str,
    data: object | None = None,
) -> JSONResponse:
    """构造统一错误响应。"""
    return JSONResponse(
        status_code=status_code,
        content=APIResponse.fail(message=message, data=data).model_dump(mode="json"),
    )


def format_validation_errors(
    exc: RequestValidationError,
) -> list[dict[str, str]]:
    """格式化请求参数校验错误。"""
    formatted_errors: list[dict[str, str]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg") or "参数无效")
        formatted_errors.append({"field": location, "message": message})
    return formatted_errors


def unexpected_error_message(exc: Exception) -> str:
    """按调试配置返回未预期异常消息。"""
    if settings.app_debug:
        return str(exc) or exc.__class__.__name__
    return "服务器内部错误"
