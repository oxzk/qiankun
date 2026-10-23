"""Task queries including the optimistic-lock claim used by the scheduler."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.repositories.base import Repository


class TaskRepository(Repository[Task]):
    """Tasks plus scheduler-specific claim operations."""

    model = Task

    async def get_due_tasks(
        self, now: datetime, exclude_ids: set[UUID], limit: int
    ) -> list[Task]:
        """Enabled tasks whose next_run_time has arrived, oldest first."""
        query = (
            select(Task)
            .where(
                Task.enabled.is_(True),
                Task.next_run_time.is_not(None),
                Task.next_run_time <= now,
            )
            .order_by(Task.next_run_time.asc(), Task.id.asc())
            .limit(limit)
        )
        if exclude_ids:
            query = query.where(Task.id.not_in(exclude_ids))
        return list((await self.session.execute(query)).scalars().all())

    async def claim_due_task(
        self, task_id: UUID, expected_next_run_time: datetime, new_next_run_time: datetime
    ) -> bool:
        """Advance next_run_time only if nobody else moved it; CAS on the old value."""
        result = await self.session.execute(
            update(Task)
            .where(
                Task.id == task_id,
                Task.enabled.is_(True),
                Task.next_run_time == expected_next_run_time,
            )
            .values(next_run_time=new_next_run_time)
        )
        return bool(result.rowcount)
