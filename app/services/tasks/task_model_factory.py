"""任务模型工厂。"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.infrastructure.database.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.shared.datetime import utc_now


class TaskModelFactory:
    """任务模型工厂。"""

    APPLY_FIELDS: ClassVar[tuple[str, ...]] = (
        "name", "provider_name", "provider_config",
        "cron_expression", "enabled", "timeout_seconds",
        "retry_count", "retry_interval", "notification_ids",
    )
    """任务更新可批量赋值字段。"""

    def from_create(
        self,
        payload: TaskCreate,
        next_run_time: datetime | None = None,
    ) -> Task:
        """从创建请求构造任务模型。"""
        now = utc_now()
        return Task(
            id=None,
            name=payload.name,
            provider_name=payload.provider_name,
            provider_config=payload.provider_config,
            cron_expression=payload.cron_expression,
            enabled=payload.enabled,
            timeout_seconds=payload.timeout_seconds,
            retry_count=payload.retry_count,
            retry_interval=payload.retry_interval,
            notification_ids=payload.notification_ids,
            notify_strategy=payload.notify_strategy.value,
            next_run_time=next_run_time,
            created_at=now,
            updated_at=now,
        )

    def apply_update(self, task: Task, payload: TaskUpdate) -> None:
        """将更新请求字段赋值到任务模型。"""
        for field in self.APPLY_FIELDS:
            setattr(task, field, getattr(payload, field))
        task.notify_strategy = payload.notify_strategy.value
