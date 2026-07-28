"""服务层分页结果对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")
"""分页条目类型。"""


@dataclass(frozen=True, slots=True)
class PageQuery:
    """服务层分页查询参数。"""

    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class PagedResult(Generic[ItemT]):
    """服务层分页结果。"""

    items: list[ItemT]
    total: int
    page: int
    page_size: int
    enums: dict[str, list[dict[str, str]]] = field(default_factory=dict)
