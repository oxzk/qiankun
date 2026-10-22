"""统计 API 结构。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StatsOut(BaseModel):
    """系统统计响应。"""

    model_config = ConfigDict(from_attributes=True)

    total_tasks: int = Field(description="任务总数")
    active_tasks: int = Field(description="启用任务数")
    executions_by_status: dict[str, int] = Field(default_factory=dict, description="执行状态统计")
