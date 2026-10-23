"""Cron next-run calculation with skip-missed-points semantics."""

from __future__ import annotations

from datetime import datetime

from croniter import croniter

from app.core.exceptions import ValidationError


def validate_cron(expression: str) -> None:
    """Raise ValidationError when croniter cannot parse the expression."""
    try:
        croniter(expression)
    except (ValueError, KeyError) as error:
        raise ValidationError(f"无效的 cron 表达式: {expression}") from error


def calculate_next_run_time(
    cron_expression: str, base_time: datetime, minimum_time: datetime | None = None
) -> datetime:
    """Next fire after base_time; skip every point at or before minimum_time."""
    cron = croniter(cron_expression, base_time)
    next_run_time: datetime = cron.get_next(datetime)
    if minimum_time is None:
        return next_run_time
    while next_run_time <= minimum_time:
        next_run_time = cron.get_next(datetime)
    return next_run_time
