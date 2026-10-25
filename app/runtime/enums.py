"""Integer enums shared by the database and the scheduling engine."""

from __future__ import annotations

from enum import IntEnum


class ExecutionStatus(IntEnum):
    """Lifecycle of one execution row."""

    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4
    TIMEOUT = 5

    @property
    def is_terminal(self) -> bool:
        """Terminal statuses are never resumed."""
        return self in {self.COMPLETED, self.FAILED, self.CANCELLED, self.TIMEOUT}


class TriggerType(IntEnum):
    """What caused an execution to start."""

    AUTO = 0
    MANUAL = 1
    RETRY = 2


class NotifyStrategy(IntEnum):
    """When task-level notifications are dispatched."""

    ALWAYS = 0
    ON_SUCCESS = 1
    ON_FAILURE = 2
    NEVER = 3


ENUM_REGISTRY: dict[str, list[dict[str, int | str]]] = {
    "execution_status": [
        {"value": int(status), "name": status.name.lower()} for status in ExecutionStatus
    ],
    "trigger_type": [{"value": int(t), "name": t.name.lower()} for t in TriggerType],
    "notify_strategy": [{"value": int(s), "name": s.name.lower()} for s in NotifyStrategy],
}
