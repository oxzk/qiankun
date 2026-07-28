"""任务重试策略。"""

from __future__ import annotations

from app.infrastructure.database.models.task import Task
from app.services.tasks.task_attempt_executor import TaskAttemptResult
from app.shared.enums import ExecutionStatus


class TaskRetryPolicy:
    """任务重试策略。"""

    def should_retry(
        self,
        task: Task,
        attempt: int,
        result: TaskAttemptResult,
    ) -> bool:
        """判断当前执行结果是否需要重试。"""
        if result.status == ExecutionStatus.SUCCESS:
            return False
        if result.status == ExecutionStatus.CANCELLED:
            return False
        return attempt < task.retry_count

    def retry_delay_seconds(self, task: Task) -> int:
        """返回重试等待秒数。"""
        return task.retry_interval
