"""通知领域服务装配。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.http.requester import Requester
from app.infrastructure.database.unit_of_work import UnitOfWorkFactory
from app.services.notifications.notification_channel_service import (
    NotificationChannelService,
)
from app.services.notifications.notification_dispatch_service import (
    NotificationDispatchService,
)
from app.services.notifications.notification_model_factory import NotificationModelFactory
from app.infrastructure.notifications.notification_sender import NotificationSender


@dataclass(slots=True)
class NotificationServices:
    """通知领域服务集合。"""

    channel: NotificationChannelService
    dispatch: NotificationDispatchService


def build_notification_services(
    requester: Requester,
    uow_factory: UnitOfWorkFactory,
) -> NotificationServices:
    """构造通知领域服务集合。"""
    notifier = NotificationSender(requester=requester)
    factory = NotificationModelFactory()
    channel = NotificationChannelService(
        notifier=notifier,
        factory=factory,
        uow_factory=uow_factory,
    )
    dispatch = NotificationDispatchService(notifier=notifier, uow_factory=uow_factory)
    return NotificationServices(
        channel=channel,
        dispatch=dispatch,
    )
