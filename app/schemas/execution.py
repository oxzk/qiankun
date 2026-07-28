"""执行记录 API 结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import ExecutionStatus, TriggerType


class ExecutionOut(BaseModel):
    """执行记录响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="执行记录 ID")
    task_id: int = Field(description="任务 ID")
    task_name: str | None = Field(default=None, description="任务名称")
    provider_name: str = Field(description="Provider 名称")
    provider_config: dict[str, Any] = Field(default_factory=dict, description="Provider 配置快照")
    trigger_type: TriggerType = Field(description="触发类型")
    status: ExecutionStatus = Field(description="执行状态")
    started_at: datetime = Field(description="开始时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")
    duration_ms: int | None = Field(default=None, description="耗时毫秒")
    retry_attempt: int = Field(default=0, description="重试序号")
    result_message: str | None = Field(default=None, description="结果消息")
    result_data: dict[str, Any] | None = Field(default=None, description="结果数据")
    logs: list[str] = Field(default_factory=list, description="执行日志")
    error_message: str | None = Field(default=None, description="错误消息")
    error_traceback: str | None = Field(default=None, description="错误堆栈")

    @field_validator("logs", mode="before")
    @classmethod
    def default_logs(cls, value: object) -> object:
        """将历史空日志转换为空列表。"""
        if value is None:
            return []
        return value
