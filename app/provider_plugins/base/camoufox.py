"""Camoufox Provider 浏览器基类。"""

from __future__ import annotations

import time
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Protocol

from app.shared.errors import AppError


class CamoufoxContext(Protocol):
    """Camoufox 异步上下文协议。"""

    async def __aenter__(self) -> Any:
        """进入上下文并返回浏览器或上下文对象。"""

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """退出上下文并释放浏览器资源。"""


class CamoufoxFactory(Protocol):
    """Camoufox 工厂协议。"""

    def __call__(self, **kwargs: object) -> CamoufoxContext:
        """创建 Camoufox 异步上下文。"""


class BaseCamoufox:
    """Camoufox 浏览器包装基类。"""

    DEFAULT_TIMEOUT = 50
    """默认页面超时时间, 单位为秒。"""

    def __init__(self) -> None:
        """初始化浏览器运行状态。"""
        self._camoufox: CamoufoxContext | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._persistent_context = False

    @property
    def page(self) -> Any:
        """返回当前页面。"""
        if self._page is None:
            raise AppError("Camoufox 页面未初始化, 请先调用 launch()")
        return self._page

    def set_page(self, page: Any) -> None:
        """设置当前页面。"""
        self._page = page

    def latest_page(self) -> Any:
        """返回当前上下文中的最后一个页面。"""
        pages = self._context.pages if self._context is not None else []
        if pages:
            return pages[-1]
        if self._page is not None:
            return self._page
        raise AppError("Camoufox 页面未初始化, 请先调用 launch()")

    @staticmethod
    def _load_camoufox_class() -> CamoufoxFactory:
        """延迟导入 Camoufox 可选依赖。"""
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError as exc:
            raise AppError("未安装 camoufox 依赖, 请安装后再使用 BaseCamoufox") from exc
        return AsyncCamoufox

    async def launch(
        self,
        headless: bool | Literal["virtual"] = False,
        proxy: str | None = None,
        user_data_dir: str | Path | None = None,
        context_options: dict[str, object] | None = None,
        **launch_options: object,
    ) -> Any:
        """启动 Camoufox 浏览器并创建页面。

        Args:
            headless: 无头模式. True 无头, False 有界面, ``"virtual"`` 使用虚拟显示.
            proxy: 代理地址.
            user_data_dir: 持久化用户数据目录.
            context_options: 浏览器上下文额外选项.
            **launch_options: 透传给 Camoufox 的启动参数.
        """
        if self._page is not None:
            return self._page

        camoufox_class = self._load_camoufox_class()
        merged_launch_options: dict[str, object] = {"headless": headless}
        if proxy:
            merged_launch_options["proxy"] = {"server": proxy}
        merged_launch_options.update(launch_options)

        merged_context_options: dict[str, object] = {"no_viewport": True}
        if context_options:
            merged_context_options.update(context_options)

        if user_data_dir is not None:
            merged_launch_options.update(merged_context_options)
            merged_launch_options["persistent_context"] = True
            merged_launch_options["user_data_dir"] = user_data_dir
            self._persistent_context = True

        self._camoufox = camoufox_class(**merged_launch_options)
        browser_or_context = await self._camoufox.__aenter__()
        if hasattr(browser_or_context, "new_page"):
            self._context = browser_or_context
        else:
            self._browser = browser_or_context
            self._context = await self._browser.new_context(**merged_context_options)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.DEFAULT_TIMEOUT * 1000)
        return self._page

    async def close(self) -> None:
        """关闭 Camoufox 相关资源。"""
        if self._page is not None and not self._persistent_context:
            await self._page.close()
        self._page = None

        if self._context is not None and not self._persistent_context:
            await self._context.close()
        self._context = None

        if self._camoufox is not None:
            await self._camoufox.__aexit__(None, None, None)
        self._camoufox = None
        self._browser = None
        self._persistent_context = False

    async def click_and_wait_for_page(self, locator: Any, timeout: float | None = None) -> Any:
        """点击目标元素并等待新标签页。"""
        if self._context is None:
            raise AppError("Camoufox 上下文未初始化, 请先调用 launch()")

        async with self._context.expect_page() as new_page_info:
            await locator.click(timeout=timeout, force=True)
        new_page = await new_page_info.value
        new_page.set_default_timeout(self.DEFAULT_TIMEOUT * 1000)
        self.set_page(new_page)
        return new_page

    async def evaluate(self, script: str, arg: object | None = None) -> object:
        """在页面上下文执行 JavaScript。"""
        return await self.page.evaluate(script, arg)

    async def screenshot(self, path: str, full_page: bool = True) -> None:
        """保存页面截图。"""
        await self.page.screenshot(path=path, full_page=full_page, type="png")

    @staticmethod
    def filter_valid_cookies(
        cookies: list[dict[str, object]],
        now: float | None = None,
    ) -> list[dict[str, object]]:
        """返回未过期的 Cookie 列表。"""
        current_time = time.time() if now is None else now
        valid_cookies: list[dict[str, object]] = []
        for cookie in cookies:
            expires = cookie.get("expires")
            if expires is None or expires == -1:
                valid_cookies.append(cookie)
                continue
            try:
                expires_at = float(expires)
            except (TypeError, ValueError):
                valid_cookies.append(cookie)
                continue
            if expires_at > current_time:
                valid_cookies.append(cookie)
        return valid_cookies

    async def get_cookies(self) -> list[dict[str, object]]:
        """获取当前页面可访问且未过期的 Cookie。"""
        cookies = await self.page.context.cookies(self.page.url)
        return self.filter_valid_cookies(cookies)

    async def has_cookie(self, name: str) -> bool:
        """按名称模糊匹配判断指定 Cookie 是否存在。"""
        cookies = await self.get_cookies()
        return any(name in str(cookie.get("name", "")) for cookie in cookies)

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """跳转到指定地址。"""
        await self.page.goto(url, wait_until=wait_until)

    def current_url(self) -> str:
        """返回当前页面 URL。"""
        return str(self.page.url)

    async def title(self) -> str:
        """返回当前页面标题。"""
        return str(await self.page.title())

    async def wait_for_timeout(self, timeout_ms: float) -> None:
        """等待指定毫秒数。"""
        await self.page.wait_for_timeout(timeout_ms)

    async def wait_for_load_state(self, state: str = "networkidle") -> None:
        """等待页面达到指定加载状态。"""
        await self.page.wait_for_load_state(state)

    async def wait_for_url(
        self,
        url: str | object,
        *,
        wait_until: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """等待当前页面 URL 匹配指定条件。

        Args:
            url: 目标 URL 字符串, 正则, 或 ``(url: str) -> bool`` 判定函数.
            wait_until: 匹配后额外等待的加载状态, 可选.
            timeout: 最长等待毫秒数; ``None`` 使用页面默认超时.
        """
        await self.page.wait_for_url(url, wait_until=wait_until, timeout=timeout)

    def locator(self, selector: str) -> Any:
        """按 CSS/文本选择器创建定位器。"""
        return self.page.locator(selector)

    async def handle_turnstile(
        self,
        timeout: float = 30_000,
        click_interval: float = 8_000,
        max_clicks: int = 3,
    ) -> bool:
        """处理 Cloudflare Turnstile 复选框验证。

        Args:
            timeout: 最大处理时长, 单位为毫秒。
            click_interval: 两次点击尝试之间的等待时长, 单位为毫秒。
            max_clicks: 最大点击尝试次数。

        Returns:
            是否已点击并观察到响应令牌生成。
        """
        from app.provider_plugins.base.turnstile import TurnstileHandler

        handler = TurnstileHandler(self.latest_page())
        return await handler.handle(
            timeout=timeout / 1000,
            click_interval=click_interval / 1000,
            max_clicks=max_clicks,
        )
