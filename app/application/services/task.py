"""Task CRUD with cron validation, enable/disable and manual triggering."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.pagination import Page, paginate
from app.application.services.scheduler.calculator import calculate_next_run_time, validate_cron
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.utils import utc_now
from app.infrastructure.database.models.task import Task
from app.runtime.enums import NotifyStrategy
from app.runtime.provider.registry import ProviderRegistry


class TaskService:
    """Transactional task management."""

    def __init__(self, uow_factory: Any, registry: ProviderRegistry, scheduler: Any) -> None:
        """Keep the UoW factory, provider registry and scheduler handle."""
        self.uow_factory = uow_factory
        self.registry = registry
        self.scheduler = scheduler

    async def list(self, page: int, page_size: int, enabled: bool | None = None) -> Page[Task]:
        """One page of tasks, newest first."""
        async with self.uow_factory() as uow:
            rows, total = await uow.tasks.list(
                (page - 1) * page_size,
                page_size,
                Task.enabled.is_(enabled) if enabled is not None else None,
            )
            return paginate(list(rows), total, page, page_size)

    async def get(self, task_id: UUID) -> Task:
        """One task or 404."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
        if task is None:
            raise NotFoundError("任务不存在")
        return task  # type: ignore[no-any-return]

    async def create(self, values: dict[str, Any]) -> Task:
        """Validate and insert; enabled tasks get a next_run_time."""
        values = self._validate_payload(values, creating=True)
        async with self.uow_factory() as uow:
            existing = await uow.tasks.list(0, 1, Task.name == values["name"])
            if existing[0]:
                raise ConflictError("同名任务已存在")
            if values.get("enabled", True):
                values["next_run_time"] = calculate_next_run_time(
                    values["cron_expression"], utc_now()
                )
            return await uow.tasks.add(values)  # type: ignore[no-any-return]

    async def update(self, task_id: UUID, values: dict[str, Any]) -> Task:
        """Apply a partial update; cron changes recompute next_run_time."""
        values = self._validate_payload(values, creating=False)
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise NotFoundError("任务不存在")
            if "name" in values and values["name"] != task.name:
                existing = await uow.tasks.list(0, 1, Task.name == values["name"])
                if existing[0]:
                    raise ConflictError("同名任务已存在")
            if "enabled" in values and values["enabled"] is False:
                values["next_run_time"] = None
            elif values.get("enabled") is True or ("cron_expression" in values and task.enabled):
                cron = values.get("cron_expression", task.cron_expression)
                values["next_run_time"] = calculate_next_run_time(cron, utc_now())
            return await uow.tasks.update(task, values)  # type: ignore[no-any-return]

    async def delete(self, task_id: UUID) -> None:
        """Cancel a running execution first, then delete; executions cascade."""
        await self.scheduler.cancel_task(task_id)
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise NotFoundError("任务不存在")
            await uow.tasks.delete(task)

    async def set_enabled(self, task_id: UUID, enabled: bool) -> Task:
        """Enable recomputes next_run_time; disable clears it."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                raise NotFoundError("任务不存在")
            values: dict[str, Any] = {"enabled": enabled}
            if enabled:
                values["next_run_time"] = calculate_next_run_time(task.cron_expression, utc_now())
            else:
                values["next_run_time"] = None
            return await uow.tasks.update(task, values)  # type: ignore[no-any-return]

    async def run(self, task_id: UUID) -> UUID:
        """Manual trigger returning the created execution id."""
        await self.get(task_id)
        execution_id: UUID = await self.scheduler.execute_task_now(task_id)
        return execution_id

    async def cancel(self, task_id: UUID) -> bool:
        """Cancel the running execution of the task."""
        await self.get(task_id)
        cancelled: bool = await self.scheduler.cancel_task(task_id)
        return cancelled

    def _validate_payload(self, values: dict[str, Any], creating: bool) -> dict[str, Any]:
        """Normalize the incoming payload, validating provider and cron."""
        values = {k: v for k, v in values.items() if v is not None or k == "timeout"}
        if creating:
            for field_name in ("name", "provider", "cron_expression"):
                if not values.get(field_name):
                    raise ValidationError(f"缺少必填字段: {field_name}")
        if "provider" in values and values["provider"] not in self.registry:
            raise ValidationError(f"Provider '{values['provider']}' 不存在")
        if "cron_expression" in values:
            validate_cron(values["cron_expression"])
        if "config" in values:
            if not isinstance(values["config"], dict):
                raise ValidationError("config 必须是对象")
        if "notification_config" in values:
            self._validate_notification_config(values["notification_config"])
        if "timeout" in values and values["timeout"] is not None and values["timeout"] <= 0:
            raise ValidationError("timeout 必须为正整数")
        if "max_retries" in values and values["max_retries"] < 0:
            raise ValidationError("max_retries 不能为负数")
        if "retry_interval_seconds" in values and values["retry_interval_seconds"] <= 0:
            raise ValidationError("retry_interval_seconds 必须为正整数")
        return values

    def _validate_notification_config(self, config: Any) -> None:
        """Notification policy shape validation."""
        if not isinstance(config, dict):
            raise ValidationError("notification_config 必须是对象")
        channels = config.get("channels", [])
        if not isinstance(channels, list) or any(not isinstance(c, str) for c in channels):
            raise ValidationError("notification_config.channels 必须是字符串数组")
        strategy = config.get("strategy")
        if strategy is not None:
            try:
                NotifyStrategy(int(strategy))
            except (TypeError, ValueError) as error:
                raise ValidationError("notification_config.strategy 无效") from error
