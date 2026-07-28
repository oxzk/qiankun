"""通知发送目标对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.infrastructure.database.models.notification import Notification
from app.shared.enums import NotifyType


@dataclass(frozen=True, slots=True)
class NotificationTarget:
    """通知基础设施发送目标。"""

    notify_type: NotifyType
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_model(cls, notification: Notification) -> "NotificationTarget":
        """从通知模型构造发送目标。"""
        return cls(
            notify_type=NotifyType(notification.notify_type),
            config=notification.config,
        )
