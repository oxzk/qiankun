"""Provider 仓储模块。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[Provider]):
    """Provider 数据访问类。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化 Provider 仓储。"""
        super().__init__(session, Provider)

    async def get_by_name(self, name: str) -> Provider | None:
        """按名称查询 Provider。"""
        result = await self.session.execute(select(Provider).where(Provider.name == name))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        enabled: bool | None = None,
    ) -> tuple[list[Provider], int]:
        """分页查询 Provider。"""
        query = select(Provider)
        if enabled is not None:
            query = query.where(Provider.enabled.is_(enabled))

        return await self.paginate(query, page, page_size, Provider.id.desc())
