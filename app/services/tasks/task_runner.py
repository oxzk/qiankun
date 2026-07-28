"""任务执行服务。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.shared.enums import TriggerType
from app.infrastructure.database.models.task import Task
from app.services.executions.execution_lifecycle_service import ExecutionLifecycleService
from app.services.notifications.notification_dispatch_service import (
    NotificationDispatchService,
)
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.services.tasks.task_attempt_executor import (
    TaskAttemptExecutor,
    TaskAttemptResult,
)
from app.services.tasks.task_retry_policy import TaskRetryPolicy
from app.services.tasks.task_run_finalizer import TaskRunFinalizer


class TaskRunner:
    """单个任务执行服务。"""

    def __init__(
        self,
        provider: ProviderExecutionService,
        executions: ExecutionLifecycleService,
        notifications: NotificationDispatchService,
        attempt_executor: TaskAttemptExecutor | None = None,
        retry_policy: TaskRetryPolicy | None = None,
        finalizer: TaskRunFinalizer | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化单个任务执行服务。"""
        self._executions = executions
        self._attempt_executor = attempt_executor or TaskAttemptExecutor(
            provider=provider,
            executions=executions,
        )
        self._retry_policy = retry_policy or TaskRetryPolicy()
        self._finalizer = finalizer or TaskRunFinalizer(
            notifications=notifications,
            uow_factory=uow_factory,
        )
        self._uow_factory = uow_factory

    async def execute_task(
        self,
        task: Task,
        trigger_type: TriggerType,
        set_execution_id: Callable[[int], None] | None = None,
    ) -> None:
        """执行任务并按配置重试。"""
        if task.id is None:
            return
        max_attempts = task.retry_count + 1

        for attempt in range(max_attempts):
            execution = await self._executions.create_execution_record(
                task,
                trigger_type,
                attempt,
            )
            if execution.id is not None and set_execution_id is not None:
                set_execution_id(execution.id)

            try:
                result = await self._attempt_executor.execute_and_record_attempt(
                    task,
                    execution,
                    trigger_type,
                )
            except asyncio.CancelledError:
                await self._finalizer.finalize(
                    task,
                    TaskAttemptResult.cancelled(),
                )
                raise

            if not self._retry_policy.should_retry(task, attempt, result):
                await self._finalizer.finalize(task, result)
                return

            await asyncio.sleep(self._retry_policy.retry_delay_seconds(task))
