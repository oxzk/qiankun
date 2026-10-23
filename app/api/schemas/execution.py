"""Execution response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.schemas.response import ResponseModel


class ExecutionResponse(ResponseModel):
    """Serialization of the task_executions table."""

    id: UUID
    task_id: UUID
    provider: str
    config: dict[str, Any]
    trigger_type: int
    status: int
    retry_attempt: int
    metadata: dict[str, Any] = Field(alias="metadata_")
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    result_message: str | None
    result_data: dict[str, Any] | None
    logs: list[Any]
    error_message: str | None
    error_traceback: str | None
    created_at: datetime
    updated_at: datetime
