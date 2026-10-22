"""任务数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Enum as SQLEnum, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base, UTCDateTime
from app.shared.enums import NotifyStrategy, enum_values
from app.shared.datetime import utc_now


class Task(Base):
    """任务数据库模型。"""

    __tablename__ = "qk_tasks"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    notification_ids: Mapped[list[int]] = mapped_column(JSON, nullable=True, default=list)
    notify_strategy: Mapped[NotifyStrategy] = mapped_column(
        SQLEnum(
            NotifyStrategy,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
            length=20,
        ),
        nullable=False,
        default=NotifyStrategy.NEVER,
    )
    next_run_time: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_run_time: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        Index("idx_qk_tasks_enabled", "enabled"),
        Index("idx_qk_tasks_next_run_time", "next_run_time"),
        Index("idx_qk_tasks_provider_name", "provider_name"),
    )
