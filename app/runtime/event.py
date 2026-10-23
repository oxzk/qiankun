"""In-process event bus connecting executions to SSE and notifications."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.runtime.logger import redact


@dataclass(frozen=True)
class Event:
    """Immutable event emitted after state changes."""

    type: str
    execution_id: UUID | None = None
    task_id: UUID | None = None
    payload: dict[str, Any] | None = None


class EventBus:
    """Dispatch events to subscribed handlers; one failure never leaks."""

    def __init__(self) -> None:
        """Start with no handlers."""
        self._handlers: list[Any] = []

    def subscribe(self, handler: Any) -> None:
        """Register a handler once."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    async def emit(self, event: Event) -> None:
        """Redact payloads and isolate handler exceptions."""
        payload = redact(event.payload) if event.payload else None
        for handler in self._handlers:
            try:
                forwarded = Event(event.type, event.execution_id, event.task_id, payload)
                await asyncio.wait_for(handler.handle_event(forwarded), timeout=30)
            except TimeoutError:
                continue
            except Exception:
                continue
