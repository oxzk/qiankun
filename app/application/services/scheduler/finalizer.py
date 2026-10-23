"""Task last_run_time updates and notification dispatch after terminal events."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.runtime.enums import NotifyStrategy
from app.runtime.event import Event
from app.runtime.notification.models import NotificationMessage


class TaskRunFinalizer:
    """Handles terminal events: last_run_time plus notifications."""

    def __init__(self, uow_factory: Any, notification_runtime: Any, logger: Any) -> None:
        """Bind dependencies."""
        self.uow_factory = uow_factory
        self.notifications = notification_runtime
        self.logger = logger

    async def handle_event(self, event: Event) -> None:
        """Only terminal events are processed."""
        if event.type not in {
            "execution.completed",
            "execution.failed",
            "execution.timeout",
            "execution.cancelled",
        }:
            return
        status = event.type.removeprefix("execution.")
        if event.execution_id is None or event.task_id is None:
            return
        await self._touch_last_run(event.task_id)
        await self._dispatch(event.task_id, event.execution_id, status)

    async def _touch_last_run(self, task_id: UUID) -> None:
        """Record when the task last ran; next_run_time stays with the scheduler."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            if task is None:
                return
            await uow.tasks.update(task, {"last_run_time": self._now()})

    async def _dispatch(self, task_id: UUID, execution_id: UUID, status: str) -> None:
        """Deliver notifications according to the task-level policy."""
        async with self.uow_factory() as uow:
            task = await uow.tasks.get(task_id)
            execution = await uow.task_executions.get(execution_id)
            if task is None or execution is None:
                return
            policy = dict(task.notification_config or {})
            strategy = self._strategy(policy, status)
            if strategy is None:
                return
            channels = list(policy.get("channels") or [])
            title = f"任务 {task.name} {status}"
            content = self._content(execution, status)
            configs: list[tuple[str, dict[str, Any]]] = []
            for channel in channels:
                setting = await uow.system_settings.by_key("notification", channel)
                if setting is None or not setting.enabled:
                    continue
                configs.append((channel, dict(setting.value or {})))
        if not configs:
            return
        results = await asyncio.gather(
            *[
                self._deliver(channel, config, NotificationMessage(title, content))
                for channel, config in configs
            ],
            return_exceptions=True,
        )
        for channel, result in zip(channels, results, strict=False):
            if isinstance(result, BaseException):
                self.logger.warning(f"通知投递异常 channel={channel}", error=str(result))

    def _strategy(self, policy: dict[str, Any], status: str) -> str | None:
        """Resolve whether this status should notify, honoring the strategy enum."""
        raw = policy.get("strategy")
        if raw is None:
            trigger_on = policy.get("on")
            if isinstance(trigger_on, list):
                return status if status in trigger_on else None
            return status if status in {"failed", "timeout"} else None
        try:
            strategy = NotifyStrategy(int(raw))
        except (TypeError, ValueError):
            return None
        if strategy is NotifyStrategy.NEVER:
            return None
        if strategy is NotifyStrategy.ALWAYS:
            return status
        if strategy is NotifyStrategy.ON_SUCCESS:
            return status if status == "completed" else None
        return status if status in {"failed", "timeout", "cancelled"} else None

    def _content(self, execution: Any, status: str) -> str:
        """Build a concise message body from the execution row."""
        lines = [f"状态: {status}", f"执行ID: {execution.id}"]
        if execution.result_message:
            lines.append(f"结果: {execution.result_message}")
        if execution.error_message:
            lines.append(f"错误: {execution.error_message}")
        return "\n".join(lines)

    async def _deliver(
        self, channel: str, config: dict[str, Any], message: NotificationMessage
    ) -> Any:
        """Send through the runtime; exceptions are captured by gather."""
        return await self.notifications.send(channel, message, config)

    @staticmethod
    def _now() -> Any:
        """Import-time-free UTC now."""
        from app.core.utils import utc_now

        return utc_now()
