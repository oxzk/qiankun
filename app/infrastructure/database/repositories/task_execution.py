"""Execution queries: lifecycle transitions, orphan recovery and history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update

from app.infrastructure.database.models.task_execution import TaskExecution
from app.infrastructure.database.repositories.base import Repository


class TaskExecutionRepository(Repository[TaskExecution]):
    """Executions with state-machine transitions and orphan cleanup."""

    model = TaskExecution

    async def cancel_orphan_running(self, message: str) -> int:
        """Mark leftover RUNNING rows from a previous process as cancelled."""
        result = await self.session.execute(
            update(TaskExecution)
            .where(TaskExecution.status.in_([0, 1]))
            .values(
                status=4,
                finished_at=datetime.now(),
                error_message=message,
            )
        )
        return result.rowcount or 0

    async def list_by_task(self, task_id: UUID, limit: int = 20) -> list[TaskExecution]:
        """Recent attempts of one task, newest first."""
        rows = await self.session.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .order_by(TaskExecution.started_at.desc().nullslast(), TaskExecution.id.desc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def latest_result(self, task_id: UUID) -> TaskExecution | None:
        """Most recent terminal execution used by stats and summaries."""
        rows = await self.session.execute(
            select(TaskExecution)
            .where(
                TaskExecution.task_id == task_id,
                TaskExecution.status.in_([2, 3, 4, 5]),
            )
            .order_by(TaskExecution.finished_at.desc().nullslast(), TaskExecution.id.desc())
            .limit(1)
        )
        first: TaskExecution | None = rows.scalars().first()
        return first
