"""JSON 编解码工具模块。"""

from __future__ import annotations

import json
from typing import Any


def json_dumps(value: Any) -> str:
    """序列化 JSON 值。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: Any, default: Any) -> Any:
    """反序列化 JSON 值，空值返回默认值。"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return default
