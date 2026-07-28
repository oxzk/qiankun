"""任务通知服务。"""

from __future__ import annotations

import asyncio

from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.shared.enums import ENUM_LABELS, ExecutionStatus, NotifyStrategy, coerce_enum
from app.infrastructure.database.models.task import Task
from app.infrastructure.notifications.target import NotificationTarget
from app.infrastructure.notifications.notification_sender import NotificationSender


class NotificationDispatchService:
    """任务执行通知服务。"""

    def __init__(
        self,
        notifier: NotificationSender,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化任务执行通知服务。"""
        self._notifier = notifier
        self._uow_factory = uow_factory

    async def send_notifications(
        self,
        task: Task,
        status: ExecutionStatus,
        message: str,
    ) -> None:
        """按任务通知策略发送通知。"""
        if not self.should_notify(task.notify_strategy, status):
            return
        if not task.notification_ids:
            return

        async with self._uow_factory() as uow:
            notifications = await uow.notifications.get_by_ids(task.notification_ids)

        notify_message = self.build_notify_message(task, status, message)
        await asyncio.gather(
            *(
                self._notifier.send_safely(
                    NotificationTarget.from_model(notification),
                    notify_message,
                )
                for notification in notifications
            ),
            return_exceptions=True,
        )

    @staticmethod
    def should_notify(strategy: str | NotifyStrategy, status: ExecutionStatus) -> bool:
        """判断当前状态是否需要通知。"""
        notify_strategy = coerce_enum(NotifyStrategy, strategy)
        if notify_strategy == NotifyStrategy.ALWAYS:
            return True
        if notify_strategy == NotifyStrategy.ON_SUCCESS:
            return status == ExecutionStatus.SUCCESS
        if notify_strategy == NotifyStrategy.ON_FAILURE:
            return status in {
                ExecutionStatus.FAILED,
                ExecutionStatus.TIMEOUT,
                ExecutionStatus.CANCELLED,
            }
        return False

    @staticmethod
    def build_notify_message(task: Task, status: ExecutionStatus, message: str) -> str:
        """构建任务通知消息。"""
        status_label = ENUM_LABELS.get(ExecutionStatus, {}).get(status.value, status.value)
        result = message.strip() if message and message.strip() else "-"
        return (
            f"{task.name} 任务执行报告\n"
            f"状态: {status_label}\n"
            f"结果: {result}"
        )
