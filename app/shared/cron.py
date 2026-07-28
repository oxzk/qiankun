"""Cron 调度工具。"""

from __future__ import annotations

from datetime import datetime

from croniter import croniter


def calculate_next_run_time(
    cron_expression: str,
    base_time: datetime,
    minimum_time: datetime | None = None,
) -> datetime:
    """计算下一次运行时间并跳过过期计划点。"""
    cron = croniter(cron_expression, base_time)
    next_run_time = cron.get_next(datetime)
    if minimum_time is None:
        return next_run_time
    while next_run_time <= minimum_time:
        next_run_time = cron.get_next(datetime)
    return next_run_time
