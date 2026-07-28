"""任务 API 结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import NotifyStrategy


class TaskBase(BaseModel):
    """任务基础请求结构。"""

    name: str = Field(min_length=1, max_length=100, description="任务名称")
    provider_name: str = Field(min_length=1, max_length=100, description="Provider 名称")
    provider_config: dict[str, Any] = Field(default_factory=dict, description="Provider 配置")
    cron_expression: str = Field(description="Cron 表达式")
    enabled: bool = Field(default=True, description="是否启用")
    timeout_seconds: int = Field(default=300, ge=1, le=86400, description="超时秒数")
    retry_count: int = Field(default=0, ge=0, le=10, description="重试次数")
    retry_interval: int = Field(default=60, ge=1, le=86400, description="重试间隔秒数")
    notification_ids: list[int] = Field(
        default_factory=list,
        description="通知渠道 ID",
    )
    notify_strategy: NotifyStrategy = Field(default=NotifyStrategy.NEVER, description="通知策略")

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, value: str) -> str:
        """校验 Cron 表达式。"""
        text = value.strip()
        if not text:
            raise ValueError("cron_expression 不能为空")
        croniter(text)
        return text

    @field_validator("provider_name", "name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """规范化文本字段。"""
        return value.strip()

    @field_validator("notification_ids")
    @classmethod
    def normalize_notification_ids(cls, value: list[int]) -> list[int]:
        """规范化通知渠道 ID。"""
        normalized: list[int] = []
        seen: set[int] = set()
        for notification_id in value:
            if notification_id <= 0:
                raise ValueError("notification_ids 必须为正整数")
            if notification_id in seen:
                continue
            seen.add(notification_id)
            normalized.append(notification_id)
        return normalized


class TaskCreate(TaskBase):
    """创建任务请求。"""


class TaskUpdate(TaskBase):
    """更新任务请求。"""


class TaskOut(TaskBase):
    """任务响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="任务 ID")
    next_run_time: datetime | None = Field(default=None, description="下次运行时间")
    last_run_time: datetime | None = Field(default=None, description="最近运行时间")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
