"""路由响应构造。"""

from __future__ import annotations

from typing import TypeVar

from app.schemas.responses import PageResponse
from app.services.common.pagination import PagedResult

ModelT = TypeVar("ModelT")
"""分页模型类型。"""


def build_page_response_from_result(
    result: PagedResult[ModelT],
    items: list[ModelT] | None = None,
) -> PageResponse[ModelT]:
    """从服务层分页结果构造 API 分页响应。"""
    return PageResponse(
        items=result.items if items is None else items,
        enums=result.enums,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
