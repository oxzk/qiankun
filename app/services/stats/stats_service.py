"""统计服务模块。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class StatsResult:
    """系统统计服务结果。"""

    total_tasks: int
    active_tasks: int
    executions_by_status: dict[str, int] = field(default_factory=dict)


class StatsService:
    """系统统计服务。"""

    def __init__(self, uow_factory: UnitOfWorkFactory = UnitOfWork) -> None:
        """初始化系统统计服务依赖。"""
        self._uow_factory = uow_factory

    async def get_stats(self) -> StatsResult:
        """获取系统统计。"""
        async with self._uow_factory() as uow:
            total_tasks, active_tasks = await uow.tasks.get_counts()
            executions_by_status = await uow.executions.count_group_by_status()
        return StatsResult(
            total_tasks=total_tasks,
            active_tasks=active_tasks,
            executions_by_status=executions_by_status,
        )
