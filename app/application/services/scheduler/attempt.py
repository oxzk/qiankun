"""Single attempt execution: timeout, cancellation and error normalization."""

from __future__ import annotations

import asyncio
import traceback
from typing import Any
from uuid import UUID

from app.core.utils import utc_now
from app.infrastructure.database.models.task import Task
from app.infrastructure.database.models.task_execution import TaskExecution
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.runtime.browser.base import BrowserContext, BrowserRuntime
from app.runtime.enums import ExecutionStatus
from app.runtime.execution.log_stream import ExecutionLogStream
from app.runtime.logger import redact
from app.runtime.provider.base import BaseProvider
from app.runtime.provider.models import ProviderContext, ProviderResult


class StreamLogger:
    """Logger writing to loguru and the in-memory SSE stream for one execution."""

    def __init__(self, execution_id: UUID, stream: ExecutionLogStream, task_id: UUID) -> None:
        """Bind one execution to its stream."""
        self.execution_id = execution_id
        self.stream = stream
        self.task_id = task_id

    def info(self, message: str, **context: Any) -> None:
        """Info level entry."""
        self._write("INFO", message, context)

    def error(self, message: str, **context: Any) -> None:
        """Error level entry."""
        self._write("ERROR", message, context)

    def warning(self, message: str, **context: Any) -> None:
        """Warning level entry."""
        self._write("WARNING", message, context)

    def _write(self, level: str, message: str, context: dict[str, Any]) -> None:
        """Fan out to loguru and the stream; the stream applies redaction."""
        from loguru import logger as loguru_logger

        bound = loguru_logger.bind(
            execution_id=str(self.execution_id), task_id=str(self.task_id), **context
        )
        getattr(bound, level.lower())(message)
        self.stream.publish(self.execution_id, level, message, context)


class AttemptExecutor:
    """Runs one provider attempt inside asyncio.timeout and persists the terminal state."""

    def __init__(
        self, default_timeout: int, cleanup_timeout: int, stream: ExecutionLogStream
    ) -> None:
        """Keep timeouts and the log stream."""
        self.default_timeout = default_timeout
        self.cleanup_timeout = cleanup_timeout
        self.stream = stream
        self._browser_runtime: BrowserRuntime | None = None

    async def execute(
        self,
        uow: UnitOfWork,
        task: Task,
        execution: TaskExecution,
        provider: BaseProvider,
        trigger: str,
    ) -> ExecutionStatus:
        """Execute one attempt; always persist exactly one terminal state."""
        started_at = utc_now()
        logger = StreamLogger(execution.id, self.stream, task.id)
        logger.info(
            f"开始执行 attempt={execution.retry_attempt} trigger={trigger}",
            provider=task.provider,
        )
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = started_at
        await uow.task_executions.update(execution, {})

        status: ExecutionStatus
        result_message = ""
        result_data: dict[str, Any] | None = None
        error_message: str | None = None
        error_traceback: str | None = None
        provider_ctx: ProviderContext | None = None
        session_cm: Any = None
        try:
            provider_ctx = ProviderContext(
                task_id=str(task.id),
                execution_id=str(execution.id),
                trigger=trigger,
                logger=logger,
                browser=None,
            )
            if "browser" in provider.capabilities:
                browser_runtime = self._browser_runtime
                if browser_runtime is None:
                    status = ExecutionStatus.FAILED
                    error_message = "浏览器能力未配置 (browser/cdp system_settings)"
                    await self._finalize(
                        uow, execution, status, started_at, result_message, result_data,
                        error_message, error_traceback,
                    )
                    return status
                session_cm = browser_runtime.open("cdp")
                session = await session_cm.__aenter__()
                provider_ctx = ProviderContext(
                    task_id=provider_ctx.task_id,
                    execution_id=provider_ctx.execution_id,
                    trigger=trigger,
                    logger=logger,
                    browser=BrowserContext(session),
                )
            timeout = task.timeout or self.default_timeout
            provider_result: ProviderResult | None = None
            try:
                async with asyncio.timeout(timeout):
                    provider_result = await provider.run(
                        provider_ctx, dict(task.config), logger
                    )
            except TimeoutError:
                status = ExecutionStatus.TIMEOUT
                error_message = f"任务执行超时: {timeout} 秒"
            else:
                assert provider_result is not None
                status = (
                    ExecutionStatus.COMPLETED if provider_result.success else ExecutionStatus.FAILED
                )
                result_message = provider_result.message
                result_data = provider_result.data or None
        except asyncio.CancelledError:
            status = ExecutionStatus.CANCELLED
            error_message = "执行被取消"
            await self._finalize(
                uow, execution, status, started_at, result_message, result_data,
                error_message, error_traceback,
            )
            raise
        except Exception as error:
            status = ExecutionStatus.FAILED
            error_message = f"{type(error).__name__}: {error}"
            error_traceback = traceback.format_exc()
        if session_cm is not None:
            await asyncio.shield(session_cm.__aexit__(None, None, None))
        await self._finalize(
            uow, execution, status, started_at, result_message, result_data,
            error_message, error_traceback,
        )
        logger.info(f"执行结束 status={status.name.lower()}", status=status.name.lower())
        return status

    async def _finalize(
        self,
        uow: UnitOfWork,
        execution: TaskExecution,
        status: ExecutionStatus,
        started_at: Any,
        result_message: str,
        result_data: dict[str, Any] | None,
        error_message: str | None,
        error_traceback: str | None,
    ) -> None:
        """Persist terminal fields under shield so cancellation cannot drop them."""
        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        async def _write() -> None:
            """Terminal write as one short transaction."""
            persisted_logs = self.stream.collect(execution.id)
            row = await uow.task_executions.get(execution.id)
            if row is None:
                return
            await uow.task_executions.update(
                row,
                {
                    "status": int(status),
                    "finished_at": finished_at,
                    "duration_ms": duration_ms,
                    "result_message": redact(result_message) if result_message else None,
                    "result_data": redact(result_data) if result_data else None,
                    "logs": persisted_logs,
                    "error_message": error_message,
                    "error_traceback": error_traceback,
                },
            )

        await asyncio.shield(_write())

    def attach_browser_runtime(self, browser_runtime: BrowserRuntime) -> None:
        """Wire the browser runtime after assembly."""
        self._browser_runtime = browser_runtime
