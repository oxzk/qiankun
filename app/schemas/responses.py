"""API 响应结构。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应。"""

    success: bool = Field(description="请求是否成功")
    message: str = Field(default="", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")

    @model_validator(mode="before")
    @classmethod
    def wrap_success_response(cls, value: object) -> object:
        """将裸返回数据包装为成功响应。"""
        if isinstance(value, cls):
            return value
        if isinstance(value, dict) and {"success", "data"} <= set(value):
            return value
        return {"success": True, "message": "ok", "data": value}

    @classmethod
    def fail(cls, message: str, data: T | None = None) -> "APIResponse[T]":
        """构造失败响应。"""
        return cls(success=False, message=message, data=data)


class PageResponse(BaseModel, Generic[T]):
    """分页响应数据。"""

    items: list[T] = Field(default_factory=list, description="数据列表")
    enums: dict[str, list[dict[str, str]]] = Field(
        default_factory=dict,
        description="前端展示所需枚举选项",
    )
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="页码")
    page_size: int = Field(default=20, description="每页大小")
