"""任务单次执行服务。"""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass

from app.infrastructure.database.models.execution import TaskExecution
from app.infrastructure.database.models.task import Task
from app.provider_plugins.contracts import ProviderContext, ProviderResult
from app.services.executions.execution_lifecycle_service import ExecutionLifecycleService
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.shared.enums import ExecutionStatus, TriggerType

TASK_CANCELLED_MESSAGE = "任务已取消"
"""任务取消消息。"""


@dataclass(slots=True)
class TaskAttemptResult:
    """单次任务执行结果。"""

    status: ExecutionStatus
    message: str
    provider_result: ProviderResult | None = None
    error_traceback: str | None = None

    @classmethod
    def cancelled(cls) -> "TaskAttemptResult":
        """构造取消执行结果。"""
        return cls(status=ExecutionStatus.CANCELLED, message=TASK_CANCELLED_MESSAGE)


class TaskAttemptExecutor:
    """任务单次执行服务。"""

    def __init__(
        self,
        provider: ProviderExecutionService,
        executions: ExecutionLifecycleService,
    ) -> None:
        """初始化任务单次执行服务依赖。"""
        self._provider = provider
        self._executions = executions

    async def execute_and_record_attempt(
        self,
        task: Task,
        execution: TaskExecution,
        trigger_type: TriggerType,
    ) -> TaskAttemptResult:
        """执行单次任务并完成执行记录。"""
        if execution.id is None:
            return TaskAttemptResult(
                status=ExecutionStatus.FAILED,
                message="执行记录缺少 ID",
            )
        try:
            provider_result = await asyncio.wait_for(
                self._provider.run_provider(
                    task.provider_name,
                    task.provider_config,
                    self._build_context(task, execution, trigger_type),
                ),
                timeout=task.timeout_seconds,
            )
            result = TaskAttemptResult(
                status=self._status_from_provider_result(provider_result),
                message=provider_result.message,
                provider_result=provider_result,
            )
            await self._executions.finish_execution(
                execution.id,
                result.status,
                result=provider_result,
            )
            return result
        except asyncio.CancelledError:
            result = TaskAttemptResult.cancelled()
            await self._executions.finish_execution(
                execution.id,
                result.status,
                error=result.message,
            )
            raise
        except asyncio.TimeoutError:
            result = TaskAttemptResult(
                status=ExecutionStatus.TIMEOUT,
                message=f"任务执行超时: {task.timeout_seconds} 秒",
            )
            await self._executions.finish_execution(
                execution.id,
                result.status,
                error=result.message,
            )
            return result
        except Exception as exc:
            result = TaskAttemptResult(
                status=ExecutionStatus.FAILED,
                message=str(exc) or "任务执行失败",
                error_traceback=traceback.format_exc(),
            )
            await self._executions.finish_execution(
                execution.id,
                result.status,
                error=result.message,
                error_traceback=result.error_traceback,
            )
            return result

    def _build_context(
        self,
        task: Task,
        execution: TaskExecution,
        trigger_type: TriggerType,
    ) -> ProviderContext:
        """构造 Provider 执行上下文。"""
        return ProviderContext(
            task_id=task.id or 0,
            task_name=task.name,
            execution_id=execution.id,
            trigger_type=trigger_type,
        )

    def _status_from_provider_result(
        self,
        result: ProviderResult,
    ) -> ExecutionStatus:
        """按 Provider 结果映射执行状态。"""
        if result.success:
            return ExecutionStatus.SUCCESS
        return ExecutionStatus.FAILED
