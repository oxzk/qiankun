"""通知渠道数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Enum as SQLEnum, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base, UTCDateTime
from app.shared.enums import NotifyType, enum_values
from app.shared.datetime import utc_now


class Notification(Base):
    """通知渠道数据库模型。"""

    __tablename__ = "qk_notifications"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    notify_type: Mapped[NotifyType] = mapped_column(
        SQLEnum(
            NotifyType,
            values_callable=enum_values,
            native_enum=False,
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
        Index("idx_qk_notifications_enabled", "enabled"),
        Index("idx_qk_notifications_notify_type", "notify_type"),
    )
