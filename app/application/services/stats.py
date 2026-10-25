"""Dashboard statistics over tasks and executions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.models.task_execution import TaskExecution


class StatsService:
    """Aggregate counters for the overview endpoint."""

    def __init__(self, uow_factory: Any) -> None:
        """Keep the UoW factory."""
        self.uow_factory = uow_factory

    async def overview(self) -> dict[str, Any]:
        """Task totals plus execution counters grouped by status."""
        async with self.uow_factory() as uow:
            session = uow.session()
            total_tasks = (
                await session.execute(select(func.count()).select_from(Task))
            ).scalar_one()
            enabled_tasks = (
                await session.execute(
                    select(func.count()).select_from(Task).where(Task.enabled.is_(True))
                )
            ).scalar_one()
            rows = await session.execute(
                select(TaskExecution.status, func.count())
                .group_by(TaskExecution.status)
            )
            by_status = {int(status): count for status, count in rows.all()}
        return {
            "tasks": {"total": total_tasks, "enabled": enabled_tasks},
            "executions": {
                "total": sum(by_status.values()),
                "pending": by_status.get(0, 0),
                "running": by_status.get(1, 0),
                "completed": by_status.get(2, 0),
                "failed": by_status.get(3, 0),
                "cancelled": by_status.get(4, 0),
                "timeout": by_status.get(5, 0),
            },
        }
