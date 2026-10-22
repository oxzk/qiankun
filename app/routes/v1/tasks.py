"""任务 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_task_service
from app.routes.dependencies import page_query
from app.routes.response_builders import build_page_response_from_result
from app.schemas.responses import APIResponse, PageResponse
from app.services.common.pagination import PageQuery
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.tasks.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
"""任务路由。"""


@router.get("", response_model=APIResponse[PageResponse[TaskOut]])
async def list_tasks(
    pagination: PageQuery = Depends(page_query),
    enabled: bool | None = None,
    provider_name: str | None = None,
    name: str | None = None,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[PageResponse[TaskOut]]:
    """分页查询任务。"""
    return build_page_response_from_result(
        await service.list_tasks(pagination, enabled, provider_name, name),
    )


@router.post("", response_model=APIResponse[TaskOut])
async def create_task(
    payload: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[TaskOut]:
    """创建任务。"""
    return await service.create_task(payload)


@router.get("/{task_id}", response_model=APIResponse[TaskOut])
async def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[TaskOut]:
    """查询任务详情。"""
    return await service.get_task(task_id)


@router.put("/{task_id}", response_model=APIResponse[TaskOut])
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[TaskOut]:
    """更新任务。"""
    return await service.update_task(task_id, payload)


@router.delete("/{task_id}", response_model=APIResponse[None])
async def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[None]:
    """删除任务。"""
    await service.delete_task(task_id)
    return None


@router.post("/{task_id}/run", response_model=APIResponse[bool])
async def run_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[bool]:
    """手动执行任务。"""
    return await service.run_task(task_id)


@router.post("/{task_id}/cancel", response_model=APIResponse[bool])
async def cancel_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[bool]:
    """取消运行中任务。"""
    return await service.cancel_task(task_id)


@router.post("/{task_id}/enable", response_model=APIResponse[TaskOut])
async def enable_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[TaskOut]:
    """启用任务。"""
    return await service.set_enabled(task_id, True)


@router.post("/{task_id}/disable", response_model=APIResponse[TaskOut])
async def disable_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
) -> APIResponse[TaskOut]:
    """禁用任务。"""
    return await service.set_enabled(task_id, False)
