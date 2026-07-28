"""时间处理工具模块。"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def to_utc_naive(value: datetime | None) -> datetime | None:
    """转换为适合 MySQL datetime 写入的 UTC naive 时间。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def ensure_utc(value: datetime | None) -> datetime | None:
    """确保数据库读取时间带 UTC 时区。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
