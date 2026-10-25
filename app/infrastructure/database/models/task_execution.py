"""task_executions table: audit rows with configuration snapshots and persisted logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin


class TaskExecution(TimestampMixin, Base):
    """One attempt of one task, immutable after reaching a terminal status."""

    __tablename__ = "task_executions"
    __table_args__ = (
        CheckConstraint("trigger_type IN (0, 1, 2)", name="valid_trigger_type"),
        CheckConstraint("status IN (0, 1, 2, 3, 4, 5)", name="valid_status"),
        CheckConstraint("retry_attempt >= 0", name="nonnegative_retry_attempt"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique execution identifier",
    )
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Task this execution belongs to",
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Provider name snapshot at trigger time"
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="Provider configuration snapshot at trigger time"
    )
    trigger_type: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="What started this execution: 0 scheduled, 1 manual, 2 retry",
    )
    status: Mapped[int] = mapped_column(
        SmallInteger,
        index=True,
        nullable=False,
        comment=(
            "Lifecycle status: 0 pending, 1 running, 2 completed, 3 failed, 4 cancelled, 5 timeout"
        ),
    )
    retry_attempt: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
        comment="Retry sequence number within the task run, 0 for the first attempt",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
        comment="Execution metadata such as previous_execution_id",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
        comment="Execution start time in UTC",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Execution finish time in UTC",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Execution duration in milliseconds",
    )
    result_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Provider result summary"
    )
    result_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, comment="Provider structured result data"
    )
    logs: Mapped[list[Any]] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
        comment="Execution log entries persisted when the terminal state commits",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Failure summary without secrets"
    )
    error_traceback: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Full failure traceback for diagnosis"
    )
