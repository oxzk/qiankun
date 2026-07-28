"""共享错误类型。"""

from __future__ import annotations


class AppError(Exception):
    """应用业务异常。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """初始化业务异常。"""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    """资源不存在异常。"""

    def __init__(self, message: str = "资源不存在") -> None:
        """初始化资源不存在异常。"""
        super().__init__(message, status_code=404)
