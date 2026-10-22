"""任务调度时间计算器。"""

from __future__ import annotations

from datetime import datetime

from app.shared.cron import calculate_next_run_time
from app.shared.datetime import utc_now


class TaskScheduleCalculator:
    """任务调度时间计算器。"""

    def next_run_time_for_enabled_task(
        self,
        enabled: bool,
        cron_expression: str,
    ) -> datetime | None:
        """按启用状态计算任务下次运行时间。"""
        if not enabled:
            return None
        current_time = utc_now()
        return calculate_next_run_time(
            cron_expression,
            current_time,
            current_time,
        )
