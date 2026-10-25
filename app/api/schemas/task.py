"""Task request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.response import ResponseModel


class TaskCreate(ResponseModel):
    """Payload for POST /tasks."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    provider: str = Field(min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)
    cron_expression: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    timeout: int | None = Field(default=None, gt=0, le=86400)
    max_retries: int = Field(default=0, ge=0, le=10)
    retry_interval_seconds: int = Field(default=60, gt=0, le=86400)
    notification_config: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(ResponseModel):
    """PATCH semantics: omitted fields stay unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    config: dict[str, Any] | None = None
    cron_expression: str | None = Field(default=None, min_length=1, max_length=100)
    timeout: int | None = Field(default=None, gt=0, le=86400)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_interval_seconds: int | None = Field(default=None, gt=0, le=86400)
    notification_config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def reject_meaningless_nulls(self) -> TaskUpdate:
        """Only timeout accepts explicit null (clear to runtime default)."""
        for field_name in (
            "name",
            "provider",
            "config",
            "cron_expression",
            "max_retries",
            "retry_interval_seconds",
            "notification_config",
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能显式置空")
        return self


class TaskResponse(ResponseModel):
    """Serialization of the tasks table."""

    id: UUID
    name: str
    provider: str
    config: dict[str, Any]
    cron_expression: str
    enabled: bool
    timeout: int | None
    max_retries: int
    retry_interval_seconds: int
    notification_config: dict[str, Any]
    next_run_time: datetime | None
    last_run_time: datetime | None
    created_at: datetime
    updated_at: datetime
