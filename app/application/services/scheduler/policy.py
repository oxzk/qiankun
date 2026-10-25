"""Claim due tasks with an in-transaction optimistic lock on next_run_time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from app.application.services.scheduler.calculator import calculate_next_run_time
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ClaimedTask:
    """Task snapshot taken at claim time for the execution flow."""

    task_id: UUID
    scheduled_at: datetime
    task: Task


class SchedulePolicy:
    """Advance next_run_time before firing, so retries and crashes never re-fire."""

    async def schedule_due_tasks(
        self,
        uow: UnitOfWork,
        now: datetime,
        exclude_ids: set[UUID],
        available_slots: int,
    ) -> list[ClaimedTask]:
        """Claim up to available_slots tasks inside one transaction."""
        candidates = await uow.tasks.get_due_tasks(now, exclude_ids, available_slots)
        claimed: list[ClaimedTask] = []
        for task in candidates:
            scheduled_at = task.next_run_time
            if scheduled_at is None:
                continue
            new_next_run_time = calculate_next_run_time(
                task.cron_expression, scheduled_at, now
            )
            claimed_ok = await uow.tasks.claim_due_task(
                task.id, scheduled_at, new_next_run_time
            )
            if not claimed_ok:
                continue
            task.next_run_time = new_next_run_time
            claimed.append(ClaimedTask(task.id, scheduled_at, task))
        return claimed

    async def fill_missing_next_run_time(self, uow: UnitOfWork, now: datetime) -> int:
        """Recompute next_run_time for enabled tasks that lost it."""
        rows, _ = await uow.tasks.list(0, 1000, Task.enabled.is_(True))
        fixed = 0
        for task in rows:
            row = cast(Task, task)
            if row.next_run_time is not None:
                continue
            row.next_run_time = calculate_next_run_time(row.cron_expression, now)
            fixed += 1
        return fixed
