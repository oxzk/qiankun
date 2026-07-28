"""登录失败速率限制。"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.config.settings import settings
from app.shared.errors import AppError


class LoginRateLimiter:
    """基于内存滑动窗口的登录失败限流器。"""

    def __init__(
        self,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        """初始化登录限流参数。"""
        self._max_attempts = max(1, max_attempts or settings.login_rate_limit_attempts)
        self._window_seconds = max(1, window_seconds or settings.login_rate_limit_window_seconds)
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def ensure_allowed(self, key: str) -> None:
        """若超过失败上限则拒绝继续登录。"""
        self._prune(key)
        failures = self._failures.get(key)
        if failures is not None and len(failures) >= self._max_attempts:
            raise AppError(
                f"登录失败次数过多, 请 {self._window_seconds} 秒后重试",
                status_code=429,
            )

    def record_failure(self, key: str) -> None:
        """记录一次登录失败。"""
        now = time.monotonic()
        bucket = self._failures[key]
        bucket.append(now)
        self._prune(key)

    def reset(self, key: str) -> None:
        """登录成功后清空失败计数。"""
        self._failures.pop(key, None)

    def _prune(self, key: str) -> None:
        """移除窗口外的失败记录。"""
        bucket = self._failures.get(key)
        if bucket is None:
            return
        threshold = time.monotonic() - self._window_seconds
        while bucket and bucket[0] < threshold:
            bucket.popleft()
        if not bucket:
            self._failures.pop(key, None)
