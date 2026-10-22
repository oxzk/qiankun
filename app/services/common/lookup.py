"""服务层实体查询 helper。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.shared.errors import NotFoundError

EntityT = TypeVar("EntityT")


async def get_required(
    getter: Callable[[object], Awaitable[EntityT | None]],
    entity_id: object,
    message: str,
) -> EntityT:
    """按 ID 查询实体, 不存在时抛出业务错误。"""
    entity = await getter(entity_id)
    if entity is None:
        raise NotFoundError(message)
    return entity
