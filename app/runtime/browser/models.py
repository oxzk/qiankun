"""Browser capability models shared by runtime and providers."""

from __future__ import annotations

from typing import Any, Protocol


class Page(Protocol):
    """Page contract exposed to providers without leaking playwright types."""

    async def goto(self, url: str, **options: Any) -> Any: ...

    async def content(self) -> str: ...

    async def title(self) -> str: ...

    async def close(self) -> None: ...


class CDPConnection(Protocol):
    """CDP websocket endpoint for advanced clients."""

    url: str


class BrowserInstance(Protocol):
    """Lifecycle handle of one browser session."""

    async def new_page(self) -> Page: ...

    async def cdp_connection(self) -> CDPConnection: ...

    async def close(self) -> None: ...
