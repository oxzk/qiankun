"""任务执行记录模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Enum as SQLEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base, UTCDateTime
from app.shared.enums import ExecutionStatus, TriggerType, enum_values


class TaskExecution(Base):
    """任务执行记录数据库模型。"""

    __tablename__ = "qk_task_executions"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("qk_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    trigger_type: Mapped[TriggerType] = mapped_column(
        SQLEnum(
            TriggerType,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
            length=20,
        ),
        nullable=False,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(
            ExecutionStatus,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
            length=20,
        ),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    logs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_qk_task_executions_task_id", "task_id"),
        Index("idx_qk_task_executions_status", "status"),
        Index("idx_qk_task_executions_started_at", "started_at"),
    )
