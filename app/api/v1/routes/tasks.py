"""Task CRUD and lifecycle endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import Container
from app.api.schemas.pagination import PageResponse
from app.api.schemas.response import SuccessResponse
from app.api.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=SuccessResponse[PageResponse[TaskResponse]])
async def list_tasks(
    container: Container,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    enabled: bool | None = None,
) -> Any:
    """Paginated tasks, newest first."""
    return await container.tasks.list(page, page_size, enabled)


@router.post("", response_model=SuccessResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, container: Container) -> Any:
    """Create a task; enabled tasks receive a next_run_time immediately."""
    return await container.tasks.create(payload.model_dump())


@router.get("/{task_id}", response_model=SuccessResponse[TaskResponse])
async def get_task(task_id: UUID, container: Container) -> Any:
    """One task by id."""
    return await container.tasks.get(task_id)


@router.patch("/{task_id}", response_model=SuccessResponse[TaskResponse])
async def update_task(task_id: UUID, payload: TaskUpdate, container: Container) -> Any:
    """Partial update; cron changes recompute next_run_time."""
    return await container.tasks.update(task_id, payload.model_dump(exclude_unset=True))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, container: Container) -> Response:
    """Delete the task after cancelling any running execution."""
    await container.tasks.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/enable", response_model=SuccessResponse[TaskResponse])
async def enable_task(task_id: UUID, container: Container) -> Any:
    """Enable scheduling and recompute next_run_time."""
    return await container.tasks.set_enabled(task_id, True)


@router.post("/{task_id}/disable", response_model=SuccessResponse[TaskResponse])
async def disable_task(task_id: UUID, container: Container) -> Any:
    """Disable scheduling and clear next_run_time."""
    return await container.tasks.set_enabled(task_id, False)


@router.post("/{task_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_task(task_id: UUID, container: Container) -> Any:
    """Manual trigger; returns the created execution id."""
    execution_id = await container.tasks.run(task_id)
    return {"success": True, "data": {"execution_id": str(execution_id)}}


@router.post("/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(task_id: UUID, container: Container) -> Any:
    """Cancel the running execution of this task."""
    cancelled = await container.tasks.cancel(task_id)
    return {"success": True, "data": {"cancelled": cancelled}}
