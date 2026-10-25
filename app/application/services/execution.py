"""Execution queries, cancellation and SSE log streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.application.pagination import Page, paginate
from app.core.exceptions import NotFoundError
from app.infrastructure.database.models.task_execution import TaskExecution
from app.runtime.enums import ExecutionStatus
from app.runtime.execution.log_stream import LogStreamEvent


class ExecutionService:
    """Read-side of the execution history plus log endpoints."""

    def __init__(self, uow_factory: Any, stream: Any, scheduler: Any) -> None:
        """Keep the UoW factory, log stream and scheduler for cancellation."""
        self.uow_factory = uow_factory
        self.stream = stream
        self.scheduler = scheduler

    async def list(
        self,
        page: int,
        page_size: int,
        task_id: UUID | None = None,
        status: ExecutionStatus | None = None,
        trigger_type: int | None = None,
    ) -> Page[TaskExecution]:
        """Filter executions by task, status and trigger."""
        filters = [
            TaskExecution.task_id == task_id if task_id is not None else None,
            TaskExecution.status == int(status) if status is not None else None,
            TaskExecution.trigger_type == trigger_type if trigger_type is not None else None,
        ]
        async with self.uow_factory() as uow:
            rows, total = await uow.task_executions.list(
                (page - 1) * page_size,
                page_size,
                *filters,
                order_by=[TaskExecution.created_at.desc(), TaskExecution.id.desc()],
            )
            return paginate(list(rows), total, page, page_size)

    async def get(self, execution_id: UUID) -> TaskExecution:
        """One execution or 404."""
        async with self.uow_factory() as uow:
            execution = await uow.task_executions.get(execution_id)
        if execution is None:
            raise NotFoundError("执行记录不存在")
        return execution  # type: ignore[no-any-return]

    async def delete(self, execution_id: UUID) -> None:
        """Delete a terminal execution; active ones must be cancelled first."""
        execution = await self.get(execution_id)
        if not ExecutionStatus(int(execution.status)).is_terminal:
            from app.core.exceptions import ConflictError

            raise ConflictError("运行中的执行不能删除，请先取消")
        async with self.uow_factory() as uow:
            row = await uow.task_executions.get(execution_id)
            if row is not None:
                await uow.task_executions.delete(row)

    async def cancel(self, execution_id: UUID) -> TaskExecution:
        """Cancel a running execution via the scheduler registry."""
        execution = await self.get(execution_id)
        if ExecutionStatus(int(execution.status)).is_terminal:
            return execution
        cancelled = await self.scheduler.cancel_by_execution(execution_id, execution.task_id)
        if not cancelled:
            from app.core.exceptions import ConflictError

            raise ConflictError("执行不在本进程中运行")
        return await self.get(execution_id)

    def logs(self, execution_id: UUID) -> dict[str, Any]:
        """Snapshot of the in-memory log history plus terminal state."""
        history = [entry.data for entry in self.stream.history(execution_id)]
        terminal = self.stream.terminal(execution_id)
        return {
            "execution_id": str(execution_id),
            "logs": history,
            "terminal": terminal.data if terminal else None,
        }

    async def stream_logs(self, execution_id: UUID) -> AsyncIterator[str]:
        """SSE generator: subscribe first, replay history, then follow."""
        await self.get(execution_id)
        with self.stream.subscribe(execution_id) as queue:
            last_id = 0
            for entry in self.stream.history(execution_id):
                yield entry.encode()
                last_id = max(last_id, entry.id)
            terminal = self.stream.terminal(execution_id)
            if terminal is not None:
                yield terminal.encode()
                return
            idle_heartbeat = 20.0
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=idle_heartbeat)
                    entry = LogStreamEvent(event.id, event.event, event.data)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if entry.id <= last_id and entry.event != "failed":
                    continue
                last_id = max(last_id, entry.id)
                yield entry.encode()
                if entry.event in {"completed", "failed"}:
                    return
