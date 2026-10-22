"""任务调度计划服务。"""

from __future__ import annotations

from collections.abc import Callable

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWorkFactory, commit_on_success
from app.shared.cron import calculate_next_run_time
from app.shared.datetime import utc_now
from app.shared.enums import TriggerType
from app.shared.logger import logger


class SchedulePolicy:
    """任务调度计划服务。"""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        """初始化任务调度计划服务依赖。"""
        self._uow_factory = uow_factory

    async def schedule_due_tasks(
        self,
        running_task_ids: set[int],
        create_execution_task: Callable[[Task, TriggerType], None],
        *,
        available_slots: int,
    ) -> int:
        """抢占并触发到期任务, 返回成功抢占数量。"""
        if available_slots <= 0:
            return 0

        current_time = utc_now()

        async def claim_due(uow) -> list[Task]:
            """在同一事务内查询并乐观抢占到期任务。"""
            candidates = await uow.tasks.get_due_tasks(
                current_time,
                exclude_ids=running_task_ids,
                limit=available_slots,
            )
            claimed: list[Task] = []
            for task in candidates:
                if task.id is None or task.next_run_time is None:
                    continue
                scheduled_at = task.next_run_time
                new_next_run_time = calculate_next_run_time(
                    task.cron_expression,
                    scheduled_at,
                    current_time,
                )
                claimed_ok = await uow.tasks.claim_due_task(
                    task.id,
                    scheduled_at,
                    new_next_run_time,
                )
                if not claimed_ok:
                    continue
                task.next_run_time = new_next_run_time
                claimed.append(task)
            return claimed

        claimed_tasks = await commit_on_success(self._uow_factory, claim_due)
        for task in claimed_tasks:
            create_execution_task(task, TriggerType.AUTO)
        if claimed_tasks:
            logger.info("调度抢占到期任务 %s 个", len(claimed_tasks))
        return len(claimed_tasks)

    async def fill_missing_next_run_time(self) -> int:
        """补齐启用任务的下次运行时间, 返回更新数量。"""
        current_time = utc_now()

        async def fill_missing(uow) -> int:
            """补齐缺失的 next_run_time 并提交。"""
            tasks = await uow.tasks.get_active_without_next_run_time()
            for task in tasks:
                task.next_run_time = calculate_next_run_time(
                    task.cron_expression,
                    current_time,
                    current_time,
                )
                await uow.tasks.update(task)
            return len(tasks)

        return await commit_on_success(self._uow_factory, fill_missing)
