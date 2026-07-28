"""任务仓储模块。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """任务数据访问类。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化任务仓储。"""
        super().__init__(session, Task)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        enabled: bool | None = None,
        provider_name: str | None = None,
        name: str | None = None,
    ) -> tuple[list[Task], int]:
        """分页查询任务。"""
        query = select(Task)
        if enabled is not None:
            query = query.where(Task.enabled.is_(enabled))
        if provider_name:
            query = query.where(Task.provider_name == provider_name)
        normalized_name = name.strip() if name else ""
        if normalized_name:
            query = query.where(Task.name.like(f"%{normalized_name}%"))

        return await self.paginate(query, page, page_size, Task.id.desc())

    async def get_names_by_ids(self, task_ids: list[int]) -> dict[int, str]:
        """按任务 ID 批量查询名称。"""
        if not task_ids:
            return {}
        result = await self.session.execute(
            select(Task.id, Task.name).where(Task.id.in_(task_ids))
        )
        return {int(task_id): name for task_id, name in result.all()}

    async def get_due_tasks(
        self,
        current_time: datetime,
        *,
        exclude_ids: set[int] | None = None,
        limit: int | None = None,
    ) -> list[Task]:
        """查询已到期且启用的任务。"""
        query = (
            select(Task)
            .where(
                Task.enabled.is_(True),
                Task.next_run_time.is_not(None),
                Task.next_run_time <= current_time,
            )
            .order_by(Task.next_run_time.asc(), Task.id.asc())
        )
        if exclude_ids:
            query = query.where(Task.id.not_in(exclude_ids))
        if limit is not None:
            query = query.limit(max(0, limit))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def claim_due_task(
        self,
        task_id: int,
        expected_next_run_time: datetime,
        new_next_run_time: datetime,
    ) -> bool:
        """乐观抢占到期任务, 成功推进 next_run_time 后返回 True。"""
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

    async def get_active_without_next_run_time(self) -> list[Task]:
        """查询未计算下次运行时间的启用任务。"""
        result = await self.session.execute(
            select(Task)
            .where(Task.enabled.is_(True), Task.next_run_time.is_(None))
            .order_by(Task.id.asc())
        )
        return list(result.scalars().all())

    async def get_counts(self) -> tuple[int, int]:
        """统计任务总数和启用数。"""
        result = await self.session.execute(
            select(
                func.count(Task.id).label("total"),
                func.count(case((Task.enabled.is_(True), 1))).label("active"),
            )
        )
        row = result.one()
        return int(row.total or 0), int(row.active or 0)
