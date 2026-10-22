"""执行记录状态更新 helper。"""

from __future__ import annotations

from app.infrastructure.database.models.execution import TaskExecution
from app.provider_plugins.contracts import ProviderResult
from app.shared.errors import AppError
from app.shared.datetime import utc_now
from app.shared.enums import ExecutionStatus, coerce_enum


class ExecutionStateUpdater:
    """集中更新执行记录终态字段。"""

    ALLOWED_FINAL_STATUSES = {
        ExecutionStatus.SUCCESS,
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CANCELLED,
    }
    """允许从运行中流转到的终态。"""

    def finish(
        self,
        execution: TaskExecution,
        status: ExecutionStatus,
        result: ProviderResult | None = None,
        error: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        """将执行记录更新为指定终态。"""
        current_status = coerce_enum(ExecutionStatus, execution.status)
        if current_status != ExecutionStatus.RUNNING:
            raise AppError("执行记录只能从运行中状态完成")
        if status not in self.ALLOWED_FINAL_STATUSES:
            raise AppError("执行记录目标状态无效")
        execution.status = status.value
        execution.finished_at = utc_now()
        execution.duration_ms = int(
            (execution.finished_at - execution.started_at).total_seconds() * 1000
        )
        if result is not None:
            execution.result_message = result.message
            execution.result_data = result.data
            execution.logs = result.logs
        if error is not None:
            execution.error_message = error
        if error_traceback is not None:
            execution.error_traceback = error_traceback
