"""基础仓储模块。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

ModelType = TypeVar("ModelType")
"""仓储模型类型。"""


class BaseRepository(Generic[ModelType]):
    """基础数据访问类。"""

    def __init__(self, session: AsyncSession, model_cls: type[ModelType]) -> None:
        """初始化仓储会话。"""
        self.session = session
        self.model_cls = model_cls
        self._id_field = getattr(self.model_cls, "id")
        if not isinstance(self._id_field, InstrumentedAttribute):
            raise AttributeError(f"{self.model_cls.__name__} 缺少 id 字段")

    async def get_by_id(self, model_id: int) -> ModelType | None:
        """按 ID 查询模型。"""
        result = await self.session.execute(
            select(self.model_cls).where(self._id_field == model_id)
        )
        return result.scalar_one_or_none()

    async def create(self, model: ModelType) -> ModelType:
        """新增模型并刷新数据库生成字段。"""
        self.session.add(model)
        return await self._flush_refresh(model)

    async def update(self, model: ModelType) -> ModelType:
        """提交当前会话变更到事务并刷新模型。"""
        return await self._flush_refresh(model)

    async def delete(self, model: ModelType) -> None:
        """删除模型并提交当前会话变更到事务。"""
        await self.session.delete(model)
        await self.session.flush()

    async def _flush_refresh(self, model: ModelType) -> ModelType:
        """刷新会话并重载模型。"""
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def paginate(
        self,
        query: Any,
        page: int,
        page_size: int,
        order_by: Any | tuple[Any, ...],
    ) -> tuple[list[ModelType], int]:
        """按页码和排序条件执行分页查询。"""
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        order_fields = order_by if isinstance(order_by, tuple) else (order_by,)
        result = await self.session.execute(
            query.order_by(*order_fields).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), int(total)
