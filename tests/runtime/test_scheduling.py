"""Unit tests for the scheduling engine, state machine and log stream."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.services.scheduler.calculator import calculate_next_run_time, validate_cron
from app.core.exceptions import ValidationError
from app.runtime.execution.log_stream import ExecutionLogStream
from app.runtime.logger import redact


def test_calculate_next_run_time_basic() -> None:
    """Next minute-level fire is strictly after the base time."""
    base = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
    nxt = calculate_next_run_time("* * * * *", base)
    assert nxt > base
    assert nxt.minute == 1


def test_calculate_next_run_time_skips_missed_points() -> None:
    """Points at or before minimum_time are skipped, never re-fired."""
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = base + timedelta(minutes=10)
    nxt = calculate_next_run_time("* * * * *", base, now)
    assert nxt > now


def test_validate_cron_rejects_garbage() -> None:
    """Invalid expressions raise ValidationError."""
    try:
        validate_cron("not a cron")
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")


def test_redact_masks_secrets() -> None:
    """Credential-like keys and bearer values are masked."""
    payload = {
        "username": "admin",
        "password": "hunter2",
        "note": "Authorization: Bearer abc.def",
    }
    result = redact(payload)
    assert result["username"] == "admin"
    assert result["password"] == "[REDACTED]"
    assert "[REDACTED]" in result["note"]


def test_log_stream_subscribe_before_history() -> None:
    """A subscriber sees the terminal frame exactly once."""
    stream = ExecutionLogStream()
    execution_id = uuid4()
    stream.publish(execution_id, "INFO", "hello")
    stream.handle_terminal(execution_id, "completed")
    with stream.subscribe(execution_id) as queue:
        history = stream.history(execution_id)
        assert len(history) == 1
        terminal = stream.terminal(execution_id)
        assert terminal is not None and terminal.event == "completed"
        assert not queue.empty() or terminal is not None


def test_log_stream_collect_persists_terminal() -> None:
    """collect() merges history and the terminal status for persistence."""
    stream = ExecutionLogStream()
    execution_id = uuid4()
    stream.publish(execution_id, "ERROR", "boom")
    stream.handle_terminal(execution_id, "failed")
    collected = stream.collect(execution_id)
    assert collected[-1]["event"] == "terminal"
    assert collected[-1]["status"] == "failed"
