"""异步重试工具。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def async_retry(
    *,
    attempts: int,
    delay_seconds: float,
    backoff: float = 2.0,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """创建异步函数重试装饰器。"""
    normalized_attempts = max(1, attempts)
    normalized_delay = max(0.0, delay_seconds)
    normalized_backoff = max(1.0, backoff)

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """装饰异步函数。"""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """执行带退避等待的异步调用。"""
            current_delay = normalized_delay
            for attempt in range(1, normalized_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions:
                    if attempt >= normalized_attempts:
                        raise
                    if current_delay > 0:
                        await asyncio.sleep(current_delay)
                    current_delay *= normalized_backoff
            raise RuntimeError("无效的重试状态")

        return wrapper

    return decorator
