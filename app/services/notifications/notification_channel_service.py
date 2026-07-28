"""通知渠道业务服务。"""

from __future__ import annotations

from app.shared.enums import NotifyType, enum_map
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.infrastructure.database.models.notification import Notification
from app.services.common.pagination import PagedResult
from app.services.common.lookup import get_required
from app.schemas.notification import (
    NotificationCreate,
    NotificationTestRequest,
    NotificationUpdate,
)
from app.infrastructure.notifications.target import NotificationTarget
from app.services.notifications.notification_model_factory import NotificationModelFactory
from app.infrastructure.notifications.notification_sender import NotificationSender


class NotificationChannelService:
    """通知渠道业务服务。"""

    def __init__(
        self,
        notifier: NotificationSender,
        factory: NotificationModelFactory | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化通知渠道业务服务依赖。"""
        self.notifier = notifier
        self._factory = factory or NotificationModelFactory()
        self._uow_factory = uow_factory

    async def list_notifications(self, page: int, page_size: int) -> PagedResult[Notification]:
        """分页查询通知渠道。"""
        async with self._uow_factory() as uow:
            items, total = await uow.notifications.list_paginated(page, page_size)
        return PagedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            enums=enum_map(NotifyType),
        )

    async def create_notification(self, payload: NotificationCreate) -> Notification:
        """创建通知渠道。"""
        notification = self._factory.from_create(payload)
        async with self._uow_factory() as uow:
            created = await uow.notifications.create(notification)
            await uow.commit()
        return created

    async def update_notification(
        self,
        notification_id: int,
        payload: NotificationUpdate,
    ) -> Notification:
        """更新通知渠道。"""
        async with self._uow_factory() as uow:
            notification = await get_required(
                uow.notifications.get_by_id,
                notification_id,
                "通知渠道不存在",
            )
            self._factory.apply_update(notification, payload)
            updated = await uow.notifications.update(notification)
            await uow.commit()
        return updated

    async def delete_notification(self, notification_id: int) -> None:
        """删除通知渠道。"""
        async with self._uow_factory() as uow:
            notification = await get_required(
                uow.notifications.get_by_id,
                notification_id,
                "通知渠道不存在",
            )
            await uow.notifications.delete(notification)
            await uow.commit()

    async def test_notification(
        self,
        notification_id: int,
        payload: NotificationTestRequest,
    ) -> None:
        """测试通知渠道。"""
        async with self._uow_factory() as uow:
            notification = await get_required(
                uow.notifications.get_by_id,
                notification_id,
                "通知渠道不存在",
            )
        await self.notifier.send_notification(
            NotificationTarget.from_model(notification),
            payload.message,
        )
