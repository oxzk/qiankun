"""执行记录查询服务。"""

from __future__ import annotations

from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.infrastructure.database.models.execution import TaskExecution
from app.schemas.execution import ExecutionOut
from app.services.common.pagination import PageQuery, PagedResult
from app.services.common.lookup import get_required
from app.shared.enums import ExecutionStatus, TriggerType, enum_map


class ExecutionQueryService:
    """执行记录查询服务。"""

    def __init__(self, uow_factory: UnitOfWorkFactory = UnitOfWork) -> None:
        """初始化执行记录查询服务依赖。"""
        self._uow_factory = uow_factory

    async def list_executions(
        self,
        pagination: PageQuery,
        task_id: int | None = None,
        task_name: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> PagedResult[ExecutionOut]:
        """分页查询执行记录。"""
        async with self._uow_factory() as uow:
            items, total = await uow.executions.list_paginated(
                pagination.page, pagination.page_size, task_id, task_name, status
            )
            task_names = await uow.tasks.get_names_by_ids(
                list({item.task_id for item in items})
            )
        return PagedResult(
            items=[self._to_out(item, task_names.get(item.task_id)) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            enums=enum_map(ExecutionStatus, TriggerType),
        )

    async def get_execution(self, execution_id: int) -> ExecutionOut:
        """查询执行记录详情。"""
        async with self._uow_factory() as uow:
            execution = await get_required(
                uow.executions.get_by_id,
                execution_id,
                "执行记录不存在",
            )
            task_names = await uow.tasks.get_names_by_ids([execution.task_id])
        return self._to_out(execution, task_names.get(execution.task_id))

    @staticmethod
    def _to_out(execution: TaskExecution, task_name: str | None) -> ExecutionOut:
        """将执行记录模型转换为响应结构。"""
        return ExecutionOut.model_validate(execution).model_copy(update={"task_name": task_name})
