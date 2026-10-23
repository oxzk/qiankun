"""Browser driver contract plus runtime and resolver composition."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from app.core.exceptions import NotFoundError
from app.runtime.browser.models import BrowserInstance


class BrowserDriver(ABC):
    """A source of browser sessions, e.g. one remote CDP endpoint."""

    @abstractmethod
    async def open(self) -> BrowserInstance:
        """Open a session owned by the caller."""
        ...


class BrowserResolver:
    """Maps driver names to implementations and injects live settings."""

    def __init__(
        self,
        drivers: dict[str, Callable[[], BrowserDriver]],
        config: Callable[[str], dict[str, Any]],
    ) -> None:
        """Keep driver factories and a settings callback per driver name."""
        self.drivers = drivers
        self.config = config

    def driver(self, name: str) -> BrowserDriver:
        """Build the driver with current configuration from system_settings."""
        if name not in self.drivers:
            raise NotFoundError(f"Browser driver '{name}' does not exist")
        return self.drivers[name]()


class BrowserRuntime:
    """Opens browser sessions and guarantees teardown on any exit path."""

    def __init__(self, resolver: BrowserResolver) -> None:
        """Bind the resolver."""
        self.resolver = resolver

    @asynccontextmanager
    async def open(self, name: str = "cdp") -> Any:
        """Yield an instance and close it even on cancellation."""
        driver = self.resolver.driver(name)
        instance = await driver.open()
        try:
            yield instance
        finally:
            await asyncio.shield(instance.close())


class BrowserContext:
    """Safe facade handed to providers; no driver internals."""

    def __init__(self, instance: BrowserInstance) -> None:
        """Wrap the active session."""
        self._instance = instance

    async def new_page(self) -> Any:
        """Open a page in the remote context."""
        return await self._instance.new_page()

    async def cdp_connection(self) -> Any:
        """Expose the CDP websocket endpoint."""
        return await self._instance.cdp_connection()
