"""Provider 相关结构。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator



class ProviderInfo(BaseModel):
    """Provider 元信息。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Provider 名称")
    code: str = Field(description="Provider 代码")
    enabled: bool = Field(default=True, description="是否启用")


class ProviderBase(BaseModel):
    """Provider 基础请求结构。"""

    name: str = Field(min_length=1, max_length=100, description="Provider 名称")
    code: str = Field(min_length=1, description="Provider 代码")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """规范化 Provider 名称。"""
        return value.strip()


class ProviderCreate(ProviderBase):
    """创建 Provider 请求。"""


class ProviderUpdate(ProviderBase):
    """更新 Provider 请求。"""


class ProviderValidateRequest(BaseModel):
    """Provider 配置校验请求。"""

    config: dict[str, Any] = Field(default_factory=dict, description="待校验配置")


class ProviderTestRunRequest(BaseModel):
    """Provider 测试运行请求。"""

    config: dict[str, Any] = Field(default_factory=dict, description="测试运行配置")
