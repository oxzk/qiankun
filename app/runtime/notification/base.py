"""Notification driver ABC and runtime dispatch without stored credentials."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.core.exceptions import NotFoundError
from app.runtime.driver import DriverTestResult
from app.runtime.logger import Logger
from app.runtime.notification.models import NotificationMessage, NotificationResult


class NotificationDriver(ABC):
    """One external delivery service, credentials passed per call."""

    @abstractmethod
    async def send(
        self, message: NotificationMessage, config: dict[str, Any]
    ) -> NotificationResult:
        """Deliver one message."""
        ...

    @abstractmethod
    async def test(self, config: dict[str, Any]) -> DriverTestResult:
        """Validate connectivity without sending content."""
        ...


class NotificationRuntime:
    """Dispatches to registered drivers; failures never alter task state."""

    def __init__(self, drivers: dict[str, NotificationDriver], logger: Logger) -> None:
        """Bind drivers and logger."""
        self.drivers = drivers
        self.logger = logger

    async def send(
        self, name: str, message: NotificationMessage, config: dict[str, Any]
    ) -> NotificationResult:
        """Send once; unexpected errors degrade to a failed result."""
        if name not in self.drivers:
            raise NotFoundError(f"Notification channel '{name}' does not exist")
        try:
            return await self.drivers[name].send(message, config)
        except Exception:
            self.logger.error("Notification delivery failed", channel=name)
            return NotificationResult(False, name, error="Notification delivery failed")

    async def test(self, name: str, config: dict[str, Any]) -> DriverTestResult:
        """Validate one channel configuration."""
        if name not in self.drivers:
            raise NotFoundError(f"Notification channel '{name}' does not exist")
        return await self.drivers[name].test(config)


ChannelConfigResolver = Callable[[str], dict[str, Any] | None]
"""Looks up one channel's config from system_settings."""
