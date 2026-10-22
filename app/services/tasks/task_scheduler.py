"""任务调度服务。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

from app.config.settings import settings
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.services.executions.execution_lifecycle_service import ExecutionLifecycleService
from app.services.tasks.task_runner import TaskRunner
from app.services.tasks.task_schedule_policy import SchedulePolicy
from app.shared.enums import TriggerType
from app.shared.logger import logger

TASK_CANCELLED_BY_SCHEDULER_MESSAGE = "任务已由调度器取消"
"""调度器取消任务消息。"""


@dataclass(slots=True)
class RunningTaskState:
    """运行中任务状态。"""

    task: asyncio.Task[None]
    execution_id: int | None = None


class TaskScheduler:
    """任务调度生命周期服务。"""

    def __init__(
        self,
        planner: SchedulePolicy,
        runner: TaskRunner,
        executions: ExecutionLifecycleService,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
        max_concurrent_tasks: int | None = None,
        interval_seconds: int | None = None,
    ) -> None:
        """初始化调度器状态。"""
        self._running_tasks: dict[int, RunningTaskState] = {}
        self._scheduler_task: asyncio.Task[None] | None = None
        self._should_stop = False
        self._planner = planner
        self._runner = runner
        self._executions = executions
        self._uow_factory = uow_factory
        self._max_concurrent_tasks = max(
            1,
            max_concurrent_tasks or settings.scheduler_max_concurrent_tasks,
        )
        self._interval_seconds = max(
            1,
            interval_seconds or settings.scheduler_interval_seconds,
        )
        self._concurrency = asyncio.Semaphore(self._max_concurrent_tasks)

    async def start(self) -> None:
        """启动调度循环。"""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return
        await self.cleanup_orphan_executions()
        self._should_stop = False
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
        logger.info(
            "调度器已启动: interval=%ss max_concurrent=%s",
            self._interval_seconds,
            self._max_concurrent_tasks,
        )

    async def stop(self) -> None:
        """停止调度循环并取消运行中任务。"""
        self._should_stop = True
        if self._scheduler_task is not None and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._scheduler_task
        self._scheduler_task = None

        for task_id in list(self._running_tasks):
            await self.cancel_task(task_id)

    async def execute_task_now(self, task_id: int) -> bool:
        """手动触发任务执行。"""
        async with self._uow_factory() as uow:
            task = await uow.tasks.get_by_id(task_id)
        if task is None or task.id is None:
            return False
        if task.id in self._running_tasks:
            return False
        if len(self._running_tasks) >= self._max_concurrent_tasks:
            logger.warning(
                "手动触发失败, 已达并发上限 %s: task_id=%s",
                self._max_concurrent_tasks,
                task_id,
            )
            return False
        self._create_execution_task(task, TriggerType.MANUAL)
        return True

    async def cancel_task(self, task_id: int) -> bool:
        """取消运行中的任务。"""
        running = self._running_tasks.get(task_id)
        if running is None:
            return False
        running.task.cancel()
        with suppress(asyncio.CancelledError):
            await running.task
        if running.execution_id is not None:
            await self._executions.cancel_running_execution(
                running.execution_id,
                TASK_CANCELLED_BY_SCHEDULER_MESSAGE,
            )
        self._running_tasks.pop(task_id, None)
        return True

    async def cleanup_orphan_executions(self) -> None:
        """清理服务重启遗留的运行中执行记录。"""
        await self._executions.cleanup_orphan_executions()

    async def _schedule_loop(self) -> None:
        """调度主循环。"""
        consecutive_errors = 0
        while not self._should_stop:
            try:
                await self._schedule_due_tasks()
                await self._fill_missing_next_run_time()
                self._cleanup_finished_tasks()
                consecutive_errors = 0
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consecutive_errors += 1
                wait_seconds = min(30 * (2**consecutive_errors), 300)
                logger.exception("调度循环异常, %s 秒后重试: %s", wait_seconds, exc)
                await asyncio.sleep(wait_seconds)

    async def _schedule_due_tasks(self) -> None:
        """查询并触发到期任务。"""
        available_slots = self._max_concurrent_tasks - len(self._running_tasks)
        await self._planner.schedule_due_tasks(
            set(self._running_tasks),
            self._create_execution_task,
            available_slots=available_slots,
        )

    async def _fill_missing_next_run_time(self) -> None:
        """补齐启用任务的下次运行时间。"""
        await self._planner.fill_missing_next_run_time()

    def _create_execution_task(self, task: Task, trigger_type: TriggerType) -> None:
        """创建后台执行任务并登记运行状态。"""
        if task.id is None:
            return
        if task.id in self._running_tasks:
            return
        if len(self._running_tasks) >= self._max_concurrent_tasks:
            logger.warning(
                "跳过创建执行, 已达并发上限 %s: task_id=%s",
                self._max_concurrent_tasks,
                task.id,
            )
            return

        def set_execution_id(execution_id: int) -> None:
            """记录当前后台任务对应的执行记录 ID。"""
            running = self._running_tasks.get(task.id)
            if running is not None:
                running.execution_id = execution_id

        execution_task = asyncio.create_task(
            self._run_with_concurrency(task, trigger_type, set_execution_id)
        )
        execution_task.add_done_callback(
            lambda done_task: self._on_execution_task_done(task.id, done_task)
        )
        self._running_tasks[task.id] = RunningTaskState(task=execution_task)

    async def _run_with_concurrency(
        self,
        task: Task,
        trigger_type: TriggerType,
        set_execution_id,
    ) -> None:
        """在并发信号量保护下执行任务。"""
        async with self._concurrency:
            await self._runner.execute_task(task, trigger_type, set_execution_id)

    def _on_execution_task_done(
        self,
        task_id: int,
        execution_task: asyncio.Task[None],
    ) -> None:
        """清理后台任务状态并记录未捕获异常。"""
        self._running_tasks.pop(task_id, None)
        if execution_task.cancelled():
            return
        try:
            execution_task.result()
        except Exception as exc:
            logger.exception("任务后台执行异常: task_id=%s: %s", task_id, exc)

    def _cleanup_finished_tasks(self) -> None:
        """清理已结束的运行状态。"""
        finished_ids = [
            task_id
            for task_id, state in self._running_tasks.items()
            if state.task.done()
        ]
        for task_id in finished_ids:
            self._running_tasks.pop(task_id, None)

    def is_running(self, task_id: int) -> bool:
        """判断任务是否正在运行。"""
        return task_id in self._running_tasks
