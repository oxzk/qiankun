"""Scheduler main loop: poll, claim, fire, with orphan recovery and backoff."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from app.application.services.scheduler.policy import SchedulePolicy
from app.application.services.scheduler.runner import TaskRunner
from app.core.config import SchedulerSettings
from app.core.utils import utc_now
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.runtime.enums import TriggerType


@dataclass
class RunningTaskState:
    """Registration of one in-flight task."""

    asyncio_task: asyncio.Task[None]
    execution_id: UUID | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)


class TaskScheduler:
    """Single-instance polling scheduler driven by next_run_time."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        policy: SchedulePolicy,
        runner: TaskRunner,
        settings: SchedulerSettings,
    ) -> None:
        """Store dependencies and per-process state."""
        self.uow_factory = uow_factory
        self.policy = policy
        self.runner = runner
        self.settings = settings
        self._running_tasks: dict[UUID, RunningTaskState] = {}
        self._concurrency = asyncio.Semaphore(settings.max_concurrent_tasks)
        self._loop_task: asyncio.Task[None] | None = None
        self._should_stop = False

    async def start(self) -> None:
        """Recover orphans, then spawn the polling loop."""
        await self.recover_orphans()
        self._should_stop = False
        self._loop_task = asyncio.create_task(self._schedule_loop(), name="qiankun-scheduler")

    async def stop(self) -> None:
        """Stop polling, cancel running tasks, await their completion."""
        self._should_stop = True
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        for state in list(self._running_tasks.values()):
            if not state.asyncio_task.done():
                state.asyncio_task.cancel()
        for state in list(self._running_tasks.values()):
            try:
                await state.asyncio_task
            except (asyncio.CancelledError, Exception):
                pass
        self._running_tasks.clear()

    async def recover_orphans(self) -> int:
        """Cancel RUNNING/PENDING rows left by a previous process."""
        async with self.uow_factory() as uow:
            count = await uow.task_executions.cancel_orphan_running(
                "Server restarted, execution state unknown"
            )
            return int(count)

    async def schedule_due_tasks(self) -> int:
        """One poll: claim due tasks and spawn their runners."""
        now = utc_now()
        running_ids = set(self._running_tasks)
        available_slots = self.settings.max_concurrent_tasks - len(running_ids)
        if available_slots <= 0:
            return 0
        async with self.uow_factory() as uow:
            claimed = await self.policy.schedule_due_tasks(uow, now, running_ids, available_slots)
        for item in claimed:
            state = RunningTaskState(
                asyncio_task=asyncio.create_task(
                    self._run_with_concurrency(item.task_id, TriggerType.AUTO),
                    name=f"qiankun-task-{item.task_id}",
                )
            )
            state.asyncio_task.add_done_callback(lambda t: self._finished(t))
            self._running_tasks[item.task_id] = state
        return len(claimed)

    async def execute_task_now(self, task_id: UUID) -> UUID:
        """Manual trigger; rejects when the task is already running."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
        if task is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("任务不存在")
        if task_id in self._running_tasks:
            from app.core.exceptions import ConflictError

            raise ConflictError("任务正在运行中")
        available_slots = self.settings.max_concurrent_tasks - len(self._running_tasks)
        if available_slots <= 0:
            from app.core.exceptions import ConflictError

            raise ConflictError("已达到最大并发任务数")
        state = RunningTaskState(
            asyncio_task=asyncio.create_task(
                self._run_with_concurrency(task_id, TriggerType.MANUAL),
                name=f"qiankun-manual-{task_id}",
            )
        )
        state.asyncio_task.add_done_callback(lambda t: self._finished(t))
        self._running_tasks[task_id] = state
        await state.ready.wait()
        if state.execution_id is None:
            from app.core.exceptions import ConflictError

            raise ConflictError("执行记录尚未创建")
        return state.execution_id

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel the running execution of one task, if any."""
        state = self._running_tasks.get(task_id)
        if state is None or state.asyncio_task.done():
            return False
        if state.asyncio_task.cancelling() == 0:
            state.asyncio_task.cancel()
        try:
            await asyncio.shield(state.asyncio_task)
        except asyncio.CancelledError:
            pass
        return True

    async def cancel_by_execution(self, execution_id: UUID, task_id: UUID) -> bool:
        """Cancel only when this execution is the task's active one."""
        state = self._running_tasks.get(task_id)
        if state is None or state.execution_id != execution_id or state.asyncio_task.done():
            return False
        if state.asyncio_task.cancelling() == 0:
            state.asyncio_task.cancel()
        try:
            await asyncio.shield(state.asyncio_task)
        except asyncio.CancelledError:
            pass
        return True

    async def _run_with_concurrency(self, task_id: UUID, trigger: TriggerType) -> None:
        """Create the execution row, then run under the semaphore."""
        async with self._concurrency:
            execution_id = await self.runner.create_execution(task_id, trigger)
            state = self._running_tasks.get(task_id)
            if state is not None:
                state.execution_id = execution_id
                state.ready.set()
            try:
                await self.runner.run_existing(task_id, execution_id, trigger)
            except asyncio.CancelledError:
                await self.runner.cancel_execution(execution_id)
                raise

    def _finished(self, task: asyncio.Task[None]) -> None:
        """Consume exceptions and drop the registration."""
        try:
            task.exception()
        except asyncio.CancelledError:
            pass
        except Exception:
            from loguru import logger

            logger.exception("Scheduled task raised an unhandled exception")
        for key, state in list(self._running_tasks.items()):
            if state.asyncio_task is task:
                self._running_tasks.pop(key, None)

    async def _schedule_loop(self) -> None:
        """Poll forever with exponential backoff on repeated errors."""
        consecutive_errors = 0
        while not self._should_stop:
            try:
                await self.schedule_due_tasks()
                async with self.uow_factory() as uow:
                    await self.policy.fill_missing_next_run_time(uow, utc_now())
                consecutive_errors = 0
                await asyncio.sleep(self.settings.interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                consecutive_errors += 1
                wait_seconds = min(30 * (2**consecutive_errors), 300)
                from loguru import logger

                logger.exception("Scheduler loop failed; backing off")
                await asyncio.sleep(wait_seconds)
