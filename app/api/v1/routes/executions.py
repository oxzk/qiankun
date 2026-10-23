"""Execution history, cancellation and SSE log streaming."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import Container
from app.api.schemas.execution import ExecutionResponse
from app.api.schemas.pagination import PageResponse
from app.api.schemas.response import SuccessResponse
from app.runtime.enums import ExecutionStatus, TriggerType

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=SuccessResponse[PageResponse[ExecutionResponse]])
async def list_executions(
    container: Container,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    task_id: UUID | None = None,
    status_filter: ExecutionStatus | None = Query(default=None, alias="status"),  # noqa: B008
    trigger_type: TriggerType | None = None,
) -> Any:
    """Paginated execution history with task/status/trigger filters."""
    return await container.executions.list(page, page_size, task_id, status_filter, trigger_type)


@router.get("/{execution_id}", response_model=SuccessResponse[ExecutionResponse])
async def get_execution(execution_id: UUID, container: Container) -> Any:
    """Full execution audit row."""
    return await container.executions.get(execution_id)


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(execution_id: UUID, container: Container) -> Response:
    """Delete a terminal execution."""
    await container.executions.delete(execution_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{execution_id}/cancel", response_model=SuccessResponse[ExecutionResponse])
async def cancel_execution(execution_id: UUID, container: Container) -> Any:
    """Cancel a running execution."""
    return await container.executions.cancel(execution_id)


@router.get("/{execution_id}/logs")
async def execution_logs(execution_id: UUID, container: Container) -> Any:
    """Snapshot of the in-memory log history plus terminal state."""
    return container.executions.logs(execution_id)


@router.get("/{execution_id}/logs/stream")
async def execution_log_stream(execution_id: UUID, container: Container) -> StreamingResponse:
    """SSE stream of historical and live log entries."""
    return StreamingResponse(
        container.executions.stream_logs(execution_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
