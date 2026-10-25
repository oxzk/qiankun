"""system_settings table: runtime configuration including credentials and notification channels."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base, TimestampMixin

SETTING_SCOPES = (
    "auth",
    "system",
    "logging",
    "browser",
    "notification",
    "dependencies",
)
"""Scopes the CHECK constraint allows."""


class SystemSetting(TimestampMixin, Base):
    """Key-value configuration row, sensitive values redacted in responses."""

    __tablename__ = "system_settings"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_system_settings_scope_key"),
        CheckConstraint(
            "scope IN ('auth', 'system', 'logging', 'browser', 'notification', 'dependencies')",
            name="valid_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique setting identifier",
    )
    scope: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Configuration scope such as auth or notification"
    )
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Unique configuration key within the scope"
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Value type one of object, string, integer, boolean, array",
    )
    value: Mapped[dict[str, Any] | list[Any] | str | int | bool | None] = mapped_column(
        JSONB, nullable=False, comment="Configuration value, credentials redacted in responses"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
        comment="Whether this setting is active",
    )
    description: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''"), comment="Human-readable purpose"
    )
