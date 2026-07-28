"""数据备份 API 结构。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    """备份文件信息。"""

    filename: str = Field(description="备份文件名")
    created_at: datetime = Field(description="备份创建时间")
    size_bytes: int = Field(description="备份文件大小")
    table_counts: dict[str, int] = Field(default_factory=dict, description="各表记录数")
