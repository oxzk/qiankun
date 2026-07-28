"""执行记录 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_execution_query_service
from app.schemas.execution import ExecutionOut
from app.shared.enums import ExecutionStatus
from app.routes.dependencies import page_query
from app.routes.response_builders import build_page_response_from_result
from app.schemas.responses import APIResponse, PageResponse
from app.services.common.pagination import PageQuery
from app.services.executions.execution_query_service import ExecutionQueryService

router = APIRouter(prefix="/executions", tags=["executions"])
"""执行记录路由。"""


@router.get("", response_model=APIResponse[PageResponse[ExecutionOut]])
async def list_executions(
    pagination: PageQuery = Depends(page_query),
    task_id: int | None = None,
    task_name: str | None = None,
    status: ExecutionStatus | None = None,
    service: ExecutionQueryService = Depends(get_execution_query_service),
) -> APIResponse[PageResponse[ExecutionOut]]:
    """分页查询执行记录。"""
    return build_page_response_from_result(
        await service.list_executions(pagination, task_id, task_name, status),
    )


@router.get("/{execution_id}", response_model=APIResponse[ExecutionOut])
async def get_execution(
    execution_id: int,
    service: ExecutionQueryService = Depends(get_execution_query_service),
) -> APIResponse[ExecutionOut]:
    """查询执行记录详情。"""
    return await service.get_execution(execution_id)
