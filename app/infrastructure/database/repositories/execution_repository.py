"""执行记录仓储模块。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.execution import TaskExecution
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.repositories.base import BaseRepository
from app.shared.enums import ExecutionStatus


class ExecutionRepository(BaseRepository[TaskExecution]):
    """任务执行记录数据访问类。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化执行记录仓储。"""
        super().__init__(session, TaskExecution)

    async def update(self, execution: TaskExecution) -> TaskExecution:
        """更新执行记录。"""
        merged = await self.session.merge(execution)
        await self.session.flush()
        await self.session.refresh(merged)
        return merged

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        task_id: int | None = None,
        task_name: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> tuple[list[TaskExecution], int]:
        """分页查询执行记录。"""
        query = select(TaskExecution)
        if task_id is not None:
            query = query.where(TaskExecution.task_id == task_id)
        normalized_task_name = task_name.strip() if task_name else ""
        if normalized_task_name:
            query = query.join(Task, Task.id == TaskExecution.task_id).where(
                Task.name.like(f"%{normalized_task_name}%")
            )
        if status is not None:
            query = query.where(TaskExecution.status == status.value)

        return await self.paginate(
            query,
            page,
            page_size,
            (TaskExecution.started_at.desc(), TaskExecution.id.desc()),
        )

    async def cancel_orphan_running(self, finished_at: datetime, error: str) -> None:
        """将遗留运行中记录标记为已取消。"""
        await self.session.execute(
            update(TaskExecution)
            .where(TaskExecution.status == ExecutionStatus.RUNNING.value)
            .values(
                status=ExecutionStatus.CANCELLED.value,
                finished_at=finished_at,
                error_message=error,
            )
        )
        await self.session.flush()

    async def count_group_by_status(self) -> dict[str, int]:
        """按状态统计执行记录数量。"""
        result = await self.session.execute(
            select(TaskExecution.status, func.count(TaskExecution.id)).group_by(
                TaskExecution.status
            )
        )
        return {status: int(total or 0) for status, total in result.all()}
