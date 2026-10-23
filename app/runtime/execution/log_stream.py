"""Maintain bounded in-memory log history and SSE subscriptions per execution."""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.utils import utc_now
from app.runtime.logger import redact


@dataclass(frozen=True)
class LogStreamEvent:
    """One SSE frame with a monotonically increasing id."""

    id: int
    event: str
    data: dict[str, Any]

    def encode(self) -> str:
        """Serialize a complete frame; JSON keeps messages inside data."""
        return (
            f"id: {self.id}\n"
            f"event: {self.event}\n"
            f"data: {json.dumps(self.data, ensure_ascii=False, default=str)}\n\n"
        )


@dataclass
class ExecutionLogs:
    """Bounded history plus the terminal notice for one execution."""

    entries: deque[LogStreamEvent]
    terminal: LogStreamEvent | None = None
    subscribers: set[asyncio.Queue[LogStreamEvent]] = field(default_factory=set)


class ExecutionLogStream:
    """Publish logs synchronously inside one event loop with bounded queues."""

    def __init__(
        self, history_size: int = 1000, max_executions: int = 256, queue_size: int = 256
    ) -> None:
        """Set capacities for histories and per-client queues."""
        self.history_size = history_size
        self.max_executions = max_executions
        self.queue_size = queue_size
        self._logs: OrderedDict[UUID, ExecutionLogs] = OrderedDict()
        self._sequence = 0

    def _get(self, execution_id: UUID) -> ExecutionLogs:
        """Create or refresh the entry, evicting stale unsubscribed ones."""
        if execution_id not in self._logs:
            self._logs[execution_id] = ExecutionLogs(deque(maxlen=self.history_size))
        self._logs.move_to_end(execution_id)
        self._trim()
        return self._logs[execution_id]

    def _trim(self) -> None:
        """Evict oldest entries without subscribers once over capacity."""
        for key in list(self._logs)[:-1]:
            if len(self._logs) <= self.max_executions:
                break
            if not self._logs[key].subscribers:
                self._logs.pop(key)

    def publish(
        self, execution_id: UUID, level: str, message: str, context: dict[str, Any] | None = None
    ) -> None:
        """Store a redacted entry and broadcast it immediately."""
        logs = self._get(execution_id)
        self._sequence += 1
        entry = LogStreamEvent(
            self._sequence,
            "log",
            redact(
                {
                    "timestamp": utc_now().isoformat(),
                    "level": level,
                    "message": message,
                    "context": context or {},
                }
            ),
        )
        logs.entries.append(entry)
        self._broadcast(logs, entry)

    def _broadcast(self, logs: ExecutionLogs, entry: LogStreamEvent) -> None:
        """Kick slow clients with an explicit overflow frame, never block."""
        for queue in tuple(logs.subscribers):
            if queue.full():
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(
                    LogStreamEvent(
                        entry.id,
                        "failed",
                        {
                            "code": "log_stream_overflow",
                            "message": "Log consumption too slow, reconnect to read history",
                        },
                    )
                )
                logs.subscribers.remove(queue)
            else:
                queue.put_nowait(entry)

    def history(self, execution_id: UUID) -> list[LogStreamEvent]:
        """Snapshot of the retained entries for one execution."""
        return list(self._get(execution_id).entries)

    def terminal(self, execution_id: UUID) -> LogStreamEvent | None:
        """Terminal frame for late subscribers, if already finished."""
        return self._get(execution_id).terminal

    def collect(self, execution_id: UUID) -> list[dict[str, Any]]:
        """Persisted log payload: history plus the terminal status."""
        logs = self._get(execution_id)
        entries = [entry.data for entry in logs.entries]
        if logs.terminal is not None:
            entries.append({"event": "terminal", **logs.terminal.data})
        return entries

    @contextmanager
    def subscribe(self, execution_id: UUID) -> Iterator[asyncio.Queue[LogStreamEvent]]:
        """Register the queue before history is read, release deterministically."""
        logs = self._get(execution_id)
        queue: asyncio.Queue[LogStreamEvent] = asyncio.Queue(self.queue_size)
        logs.subscribers.add(queue)
        try:
            yield queue
        finally:
            logs.subscribers.discard(queue)
            self._trim()

    def handle_terminal(self, execution_id: UUID, status: str) -> None:
        """Publish the terminal frame after the database state has committed."""
        logs = self._get(execution_id)
        self._sequence += 1
        terminal = LogStreamEvent(
            self._sequence,
            "completed" if status in {"completed", "cancelled"} else "failed",
            {"status": status, "execution_id": str(execution_id)},
        )
        logs.terminal = terminal
        self._broadcast(logs, terminal)
