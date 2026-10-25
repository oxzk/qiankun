"""tasks table: task definitions with cron schedule and retry policy."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin


class Task(TimestampMixin, Base):
    """Persistent task definition consumed by the scheduler."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("timeout IS NULL OR timeout > 0", name="positive_timeout"),
        CheckConstraint("max_retries >= 0", name="nonnegative_retries"),
        CheckConstraint("retry_interval_seconds > 0", name="positive_retry_interval"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique task identifier",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="Task display name"
    )
    provider: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False, comment="Provider name used to execute the task"
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
        comment="Provider-specific task configuration validated against the provider schema",
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Five-field cron expression controlling the schedule"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        index=True,
        nullable=False,
        comment="Whether the task is enabled for scheduling",
    )
    timeout: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Execution timeout in seconds; NULL uses the runtime default",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
        comment="Maximum retries after a failed execution",
    )
    retry_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        server_default=text("60"),
        nullable=False,
        comment="Delay between retries in seconds",
    )
    notification_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
        comment="Task-level notification policy such as channels and triggering statuses",
    )
    next_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
        comment="Next scheduled run time in UTC; NULL while the task is disabled",
    )
    last_run_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last execution start time in UTC",
    )
