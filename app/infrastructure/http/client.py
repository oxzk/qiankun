"""curl-cffi based HTTP client shared by notifications and provider test runs."""

from __future__ import annotations

from typing import Any, Literal

from curl_cffi.requests import AsyncSession


class HttpClient:
    """Thin async wrapper reusing one connection pool."""

    def __init__(self) -> None:
        """Create the underlying session lazily on first use."""
        self._session: AsyncSession | None = None  # type: ignore[type-arg]

    def _ensure(self) -> Any:
        """Open the session once."""
        if self._session is None:
            self._session = AsyncSession(impersonate="chrome")
        return self._session

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        url: str,
        **kwargs: Any,
    ) -> Any:
        """Perform one HTTP request."""
        return await self._ensure().request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> Any:
        """GET convenience."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        """POST convenience."""
        return await self.request("POST", url, **kwargs)

    async def close(self) -> None:
        """Release pooled connections."""
        if self._session is not None:
            await self._session.close()
            self._session = None
