"""执行记录领域服务装配。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.database.unit_of_work import UnitOfWorkFactory
from app.services.executions.execution_lifecycle_service import ExecutionLifecycleService
from app.services.executions.execution_query_service import ExecutionQueryService


@dataclass(slots=True)
class ExecutionServices:
    """执行记录领域服务集合。"""

    query: ExecutionQueryService
    lifecycle: ExecutionLifecycleService


def build_execution_services(uow_factory: UnitOfWorkFactory) -> ExecutionServices:
    """构造执行记录领域服务集合。"""
    return ExecutionServices(
        query=ExecutionQueryService(uow_factory=uow_factory),
        lifecycle=ExecutionLifecycleService(uow_factory=uow_factory),
    )
