"""Provider 插件运行契约。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.datetime import utc_now
from app.shared.enums import TriggerType

HeadlessMode = Literal["false", "true", "virtual"]
"""浏览器无头模式: false 有界面, true 无头, virtual 虚拟显示。"""

HEADLESS_MODES: frozenset[str] = frozenset({"false", "true", "virtual"})
"""合法 headless 配置值集合。"""


class ProviderConfig(BaseModel):
    """Provider 通用配置基类。"""

    model_config = ConfigDict(extra="ignore")


class BrowserProviderConfig(ProviderConfig):
    """浏览器型 Provider 通用配置。"""

    headless: HeadlessMode = Field(
        default="true",
        description="无头模式: false|true|virtual",
    )
    proxy: str | None = Field(default=None, description="浏览器代理地址")
    user_data_dir: str | None = Field(default=None, description="浏览器用户数据目录")

    @field_validator("headless", mode="before")
    @classmethod
    def normalize_headless(cls, value: object) -> HeadlessMode:
        """规范化 headless 配置为 false|true|virtual。"""
        if value is None:
            return "true"
        text = str(value).strip().lower()
        if text not in HEADLESS_MODES:
            raise ValueError("headless 仅支持 false|true|virtual")
        return text  # type: ignore[return-value]

    @field_validator("proxy", "user_data_dir", mode="before")
    @classmethod
    def normalize_optional_browser_text(cls, value: object) -> str | None:
        """规范化可选浏览器文本配置。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def resolve_headless(self) -> bool | Literal["virtual"]:
        """将 headless 配置解析为 Camoufox 启动参数。"""
        if self.headless == "virtual":
            return "virtual"
        return self.headless == "true"


class ProviderContext(BaseModel):
    """Provider 执行上下文。"""

    task_id: int = Field(description="任务 ID")
    task_name: str = Field(description="任务名称")
    execution_id: int | None = Field(default=None, description="执行记录 ID")
    trigger_type: TriggerType = Field(description="触发类型")


class ProviderResult(BaseModel):
    """Provider 执行结果。"""

    success: bool = Field(description="是否成功")
    message: str = Field(default="", description="结果消息")
    data: dict[str, Any] = Field(default_factory=dict, description="结果数据")
    logs: list[str] = Field(default_factory=list, description="执行日志")

    @classmethod
    def ok(
        cls,
        message: str = "执行成功",
        data: dict[str, Any] | None = None,
        logs: list[str] | None = None,
    ) -> "ProviderResult":
        """构造成功结果。"""
        return cls(success=True, message=message, data=data or {}, logs=logs or [])

    @classmethod
    def fail(
        cls,
        message: str = "执行失败",
        data: dict[str, Any] | None = None,
        logs: list[str] | None = None,
    ) -> "ProviderResult":
        """构造失败结果。"""
        return cls(success=False, message=message, data=data or {}, logs=logs or [])


def format_provider_log(content: str) -> str:
    """按 Provider 日志格式构造单行日志。"""
    return f"{utc_now().strftime('%Y-%m-%d %H:%M:%S')}: {content}"


class ProviderValidateResult(BaseModel):
    """Provider 配置校验结果。"""

    valid: bool = Field(description="配置是否合法")
    config: dict[str, Any] | None = Field(default=None, description="规范化配置")
    error: str | None = Field(default=None, description="错误信息")
