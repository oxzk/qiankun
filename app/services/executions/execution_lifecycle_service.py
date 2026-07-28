"""执行记录生命周期服务。"""

from __future__ import annotations

from app.infrastructure.database.models.execution import TaskExecution
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.provider_plugins.contracts import ProviderResult
from app.services.executions.execution_state_machine import ExecutionStateUpdater
from app.shared.datetime import utc_now
from app.shared.enums import ExecutionStatus, TriggerType


class ExecutionLifecycleService:
    """执行记录生命周期服务。"""

    def __init__(
        self,
        state_updater: ExecutionStateUpdater | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化执行记录生命周期服务依赖。"""
        self._state_updater = state_updater or ExecutionStateUpdater()
        self._uow_factory = uow_factory

    async def cleanup_orphan_executions(self) -> None:
        """清理服务重启遗留的运行中执行记录。"""
        async with self._uow_factory() as uow:
            await uow.executions.cancel_orphan_running(
                finished_at=utc_now(),
                error="Server restarted, execution state unknown",
            )

    async def create_execution_record(
        self,
        task: Task,
        trigger_type: TriggerType,
        retry_attempt: int,
    ) -> TaskExecution:
        """创建执行记录。"""
        execution = TaskExecution(
            id=None,
            task_id=task.id or 0,
            provider_name=task.provider_name,
            provider_config=task.provider_config,
            trigger_type=trigger_type.value,
            status=ExecutionStatus.RUNNING.value,
            started_at=utc_now(),
            retry_attempt=retry_attempt,
        )
        async with self._uow_factory() as uow:
            created = await uow.executions.create(execution)
            await uow.commit()
            return created

    async def finish_execution(
        self,
        execution_id: int,
        status: ExecutionStatus,
        result: ProviderResult | None = None,
        error: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        """完成执行记录。"""
        async with self._uow_factory() as uow:
            execution = await uow.executions.get_by_id(execution_id)
            if execution is None:
                return
            self._state_updater.finish(
                execution,
                status,
                result=result,
                error=error,
                error_traceback=error_traceback,
            )
            await uow.executions.update(execution)
            await uow.commit()

    async def cancel_running_execution(self, execution_id: int, reason: str) -> None:
        """取消指定运行中执行记录。"""
        async with self._uow_factory() as uow:
            execution = await uow.executions.get_by_id(execution_id)
            if execution is None:
                return
            if ExecutionStatus(execution.status) != ExecutionStatus.RUNNING:
                return
            self._state_updater.finish(
                execution,
                ExecutionStatus.CANCELLED,
                error=reason,
            )
            await uow.executions.update(execution)
            await uow.commit()
