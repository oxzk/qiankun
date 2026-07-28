"""路由依赖。"""

from __future__ import annotations

from fastapi import Query

from app.services.common.pagination import PageQuery


def page_query(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageQuery:
    """返回服务层分页查询参数。"""
    return PageQuery(page=page, page_size=page_size)
