"""Execution flow per task run: creation, attempt loop and cancellation."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.application.services.scheduler.attempt import AttemptExecutor
from app.core.utils import utc_now
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.models.task_execution import TaskExecution
from app.runtime.enums import ExecutionStatus, TriggerType
from app.runtime.provider.registry import ProviderRegistry


class TaskRunner:
    """One execution row per attempt; retries keep the task slot."""

    def __init__(
        self, uow_factory: Any, registry: ProviderRegistry, executor: AttemptExecutor
    ) -> None:
        """Bind dependencies used by every attempt."""
        self.uow_factory = uow_factory
        self.registry = registry
        self.executor = executor

    async def create_execution(self, task_id: UUID, trigger: TriggerType) -> UUID:
        """Insert the first PENDING row so callers get an id immediately."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise RuntimeError(f"Task {task_id} vanished before execution")
            execution = await uow.task_executions.add(
                {
                    "task_id": task.id,
                    "provider": task.provider,
                    "config": dict(task.config),
                    "trigger_type": int(trigger),
                    "status": int(ExecutionStatus.PENDING),
                    "retry_attempt": 0,
                    "metadata_": {},
                }
            )
            return execution.id  # type: ignore[no-any-return]

    async def run_existing(self, task_id: UUID, execution_id: UUID, trigger: TriggerType) -> None:
        """Run the attempt loop starting from an existing PENDING row."""
        attempt = 0
        current_execution_id = execution_id
        trigger_type = trigger
        while True:
            task, execution = await self._load_pair(task_id, current_execution_id)
            if task is None or execution is None:
                return
            try:
                provider = self.registry.get(task.provider)
            except Exception:
                await self._fail_missing_provider(task_id, current_execution_id, task.provider)
                return
            try:
                async with self.uow_factory() as uow:
                    task_row = await uow.tasks.get(task.id)
                    execution_row = await uow.task_executions.get(execution.id)
                    if task_row is None or execution_row is None:
                        return
                    status = await self.executor.execute(
                        uow, task_row, execution_row, provider, trigger_type.name.lower()
                    )
            except asyncio.CancelledError:
                raise
            if status in {ExecutionStatus.COMPLETED, ExecutionStatus.CANCELLED}:
                return
            if attempt >= task.max_retries:
                return
            attempt += 1
            trigger_type = TriggerType.RETRY
            current_execution_id = await self._create_retry(
                task_id, attempt, current_execution_id
            )
            await asyncio.sleep(task.retry_interval_seconds)

    async def cancel_execution(self, execution_id: UUID) -> None:
        """Best-effort terminal CANCELLED write after task cancellation."""
        async with self.uow_factory() as uow:
            execution = await uow.task_executions.get(execution_id)
            if execution is None or int(execution.status) in {2, 3, 4, 5}:
                return
            await uow.task_executions.update(
                execution,
                {
                    "status": int(ExecutionStatus.CANCELLED),
                    "finished_at": utc_now(),
                    "error_message": "执行被取消",
                },
            )

    async def _load_pair(
        self, task_id: UUID, execution_id: UUID
    ) -> tuple[Task | None, TaskExecution | None]:
        """Load the current task and execution rows."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            execution = await uow.task_executions.get(execution_id)
            return task, execution

    async def _create_retry(self, task_id: UUID, attempt: int, previous_id: UUID) -> UUID:
        """Insert the retry row linked to the previous attempt."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise RuntimeError(f"Task {task_id} vanished during retries")
            execution = await uow.task_executions.add(
                {
                    "task_id": task.id,
                    "provider": task.provider,
                    "config": dict(task.config),
                    "trigger_type": int(TriggerType.RETRY),
                    "status": int(ExecutionStatus.PENDING),
                    "retry_attempt": attempt,
                    "metadata_": {"previous_execution_id": str(previous_id)},
                }
            )
            return execution.id  # type: ignore[no-any-return]

    async def _fail_missing_provider(
        self, task_id: UUID, execution_id: UUID, provider: str
    ) -> None:
        """Terminal failure when the provider is not registered."""
        async with self.uow_factory() as uow:
            execution = await uow.task_executions.get(execution_id)
            if execution is None:
                return
            await uow.task_executions.update(
                execution,
                {
                    "status": int(ExecutionStatus.FAILED),
                    "finished_at": utc_now(),
                    "error_message": f"Provider '{provider}' does not exist",
                },
            )
