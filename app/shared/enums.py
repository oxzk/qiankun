"""业务枚举定义。"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar


class NotifyStrategy(StrEnum):
    """通知策略枚举。"""

    NEVER = "never"
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    ON_SUCCESS = "on_success"


class NotifyType(StrEnum):
    """通知渠道类型枚举。"""

    WEBHOOK = "webhook"
    TELEGRAM = "telegram"


class ExecutionStatus(StrEnum):
    """执行状态枚举。"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TriggerType(StrEnum):
    """触发类型枚举。"""

    AUTO = "auto"
    MANUAL = "manual"


EnumType = type[NotifyStrategy] | type[NotifyType] | type[ExecutionStatus] | type[TriggerType]
"""业务枚举类型联合。"""

EnumValueT = TypeVar("EnumValueT", bound=StrEnum)
"""业务枚举值类型。"""


ENUM_FIELD_NAMES: dict[EnumType, str] = {
    NotifyStrategy: "notify_strategy",
    NotifyType: "notify_type",
    ExecutionStatus: "status",
    TriggerType: "trigger_type",
}
"""业务枚举对应的字段名。"""


ENUM_LABELS: dict[EnumType, dict[str, str]] = {
    NotifyStrategy: {
        NotifyStrategy.NEVER.value: "不通知",
        NotifyStrategy.ALWAYS.value: "每次完成后通知",
        NotifyStrategy.ON_FAILURE.value: "仅失败时通知",
        NotifyStrategy.ON_SUCCESS.value: "仅成功时通知",
    },
    NotifyType: {
        NotifyType.WEBHOOK.value: "Webhook",
        NotifyType.TELEGRAM.value: "Telegram",
    },
    ExecutionStatus: {
        ExecutionStatus.RUNNING.value: "运行中",
        ExecutionStatus.SUCCESS.value: "成功",
        ExecutionStatus.FAILED.value: "失败",
        ExecutionStatus.TIMEOUT.value: "超时",
        ExecutionStatus.CANCELLED.value: "已取消",
    },
    TriggerType: {
        TriggerType.AUTO.value: "自动调度",
        TriggerType.MANUAL.value: "手动触发",
    },
}
"""业务枚举展示文案。"""


def enum_values(enum_type: EnumType) -> list[str]:
    """返回枚举持久化值列表。"""
    return [item.value for item in enum_type]


def enum_options(enum_type: EnumType) -> list[dict[str, str]]:
    """返回前端展示所需枚举选项。"""
    labels = ENUM_LABELS[enum_type]
    return [{"value": item.value, "label": labels.get(item.value, item.value)} for item in enum_type]


def enum_map(*enum_types: EnumType) -> dict[str, list[dict[str, str]]]:
    """按字段名构造前端枚举映射。"""
    return {ENUM_FIELD_NAMES[enum_type]: enum_options(enum_type) for enum_type in enum_types}


def coerce_enum(enum_type: type[EnumValueT], value: str | EnumValueT) -> EnumValueT:
    """将字符串或枚举值转换为指定业务枚举。"""
    if isinstance(value, enum_type):
        return value
    return enum_type(str(value))
