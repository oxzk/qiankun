"""通知渠道模型工厂。"""

from __future__ import annotations

from app.infrastructure.database.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate


class NotificationModelFactory:
    """通知渠道模型工厂。"""

    def from_create(self, payload: NotificationCreate) -> Notification:
        """从创建请求构造通知渠道模型。"""
        return Notification(
            id=None,
            name=payload.name,
            notify_type=payload.notify_type.value,
            config=payload.config,
            enabled=payload.enabled,
        )

    def apply_update(
        self,
        notification: Notification,
        payload: NotificationUpdate,
    ) -> None:
        """将更新请求字段赋值到通知渠道模型。"""
        notification.name = payload.name
        notification.notify_type = payload.notify_type.value
        notification.config = payload.config
        notification.enabled = payload.enabled
