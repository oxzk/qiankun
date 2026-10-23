"""CDP browser driver: the only browser capability, config from system_settings."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import async_playwright

from app.runtime.browser.models import BrowserInstance


class CDPInstance:
    """Session wrapper exposing only new_page, cdp_connection and close."""

    def __init__(self, browser: Any, context: Any, stack: AsyncExitStack) -> None:
        """Hold playwright objects and the exit stack owning teardown order."""
        self._browser = browser
        self._context = context
        self._stack = stack
        self._closed = False

    async def new_page(self) -> Any:
        """Create a page in the remote context."""
        return await self._context.new_page()

    async def cdp_connection(self) -> Any:
        """Return the underlying CDP session endpoint data."""
        return self._browser

    async def close(self) -> None:
        """Close the context once; playwright objects follow the stack."""
        if self._closed:
            return
        self._closed = True
        await self._stack.aclose()


def with_token(endpoint: str, token: Any) -> str:
    """Append the token as a query parameter, keeping existing ones."""
    if not token:
        return endpoint
    url = urlsplit(endpoint)
    query = dict(parse_qsl(url.query)) | {"token": str(token)}
    return urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment))


async def connect(endpoint: str) -> BrowserInstance:
    """Connect over CDP; only objects created here are closed on exit."""
    async with AsyncExitStack() as stack:
        playwright = await stack.enter_async_context(async_playwright())
        browser = await playwright.chromium.connect_over_cdp(endpoint)
        context = await browser.new_context()
        stack.push_async_callback(context.close)
        return CDPInstance(browser, context, stack.pop_all())
    raise RuntimeError("unreachable")


class CDPDriver:
    """Connects to the remote browser configured in system_settings browser/cdp."""

    def __init__(self, settings: dict[str, Any]) -> None:
        """Store the validated endpoint and optional token."""
        self.settings = settings

    async def open(self) -> BrowserInstance:
        """Connect using the current endpoint and token."""
        endpoint = with_token(str(self.settings["endpoint"]), self.settings.get("token"))
        return await connect(endpoint)

    async def test(self) -> Any:
        """Attempt a connection and report success or failure."""
        try:
            instance = await self.open()
        except Exception as error:
            from app.runtime.driver import DriverTestResult

            return DriverTestResult(False, f"CDP 连接失败: {type(error).__name__}")
        await instance.close()
        from app.runtime.driver import DriverTestResult

        return DriverTestResult(True, "CDP 连接成功")
