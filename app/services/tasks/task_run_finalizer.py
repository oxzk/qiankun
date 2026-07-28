"""任务运行收尾服务。"""

from __future__ import annotations

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory, commit_on_success
from app.services.notifications.notification_dispatch_service import NotificationDispatchService
from app.services.tasks.task_attempt_executor import TaskAttemptResult
from app.shared.datetime import utc_now


class TaskRunFinalizer:
    """任务运行收尾服务。"""

    def __init__(
        self,
        notifications: NotificationDispatchService,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化任务运行收尾服务依赖。"""
        self._notifications = notifications
        self._uow_factory = uow_factory

    async def finalize(self, task: Task, result: TaskAttemptResult) -> None:
        """完成任务运行收尾处理。"""
        await self._finish_task_run(task)
        await self._notifications.send_notifications(task, result.status, result.message)

    async def _finish_task_run(self, task: Task) -> None:
        """仅更新 last_run_time; next_run_time 由调度抢占或任务 CRUD 维护。"""
        if task.id is None:
            return

        async def update_task(uow: UnitOfWork) -> None:
            """更新任务最近运行时间。"""
            current_task = await uow.tasks.get_by_id(task.id)
            if current_task is None:
                return
            current_task.last_run_time = utc_now()
            await uow.tasks.update(current_task)

        await commit_on_success(self._uow_factory, update_task)
