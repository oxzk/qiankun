"""通知渠道 API 结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import NotifyType


class NotificationBase(BaseModel):
    """通知渠道基础结构。"""

    name: str = Field(min_length=1, max_length=100, description="通知渠道名称")
    notify_type: NotifyType = Field(description="通知渠道类型")
    config: dict[str, Any] = Field(default_factory=dict, description="通知渠道配置")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """规范化通知渠道名称。"""
        return value.strip()


class NotificationCreate(NotificationBase):
    """创建通知渠道请求。"""


class NotificationUpdate(NotificationBase):
    """更新通知渠道请求。"""


class NotificationTestRequest(BaseModel):
    """通知渠道测试请求。"""

    message: str = Field(default="QianKun notification test", description="测试消息")


class NotificationOut(NotificationBase):
    """通知渠道响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="通知渠道 ID")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")
