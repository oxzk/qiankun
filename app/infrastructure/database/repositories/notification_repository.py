"""通知渠道仓储模块。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.notification import Notification
from app.infrastructure.database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """通知渠道数据访问类。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化通知渠道仓储。"""
        super().__init__(session, Notification)

    async def get_by_ids(self, notification_ids: list[int]) -> list[Notification]:
        """按 ID 列表查询启用通知渠道。"""
        if not notification_ids:
            return []
        result = await self.session.execute(
            select(Notification).where(
                Notification.enabled.is_(True),
                Notification.id.in_(notification_ids),
            )
        )
        return list(result.scalars().all())

    async def get_existing_ids(self, notification_ids: list[int]) -> set[int]:
        """按 ID 列表查询存在的通知渠道 ID。"""
        if not notification_ids:
            return set()
        result = await self.session.execute(
            select(Notification.id).where(Notification.id.in_(notification_ids))
        )
        return {int(notification_id) for notification_id in result.scalars().all()}

    async def list_paginated(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[Notification], int]:
        """分页查询通知渠道。"""
        query = select(Notification)
        return await self.paginate(query, page, page_size, Notification.id.desc())
