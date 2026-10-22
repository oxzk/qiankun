"""Camoufox Provider 浏览器基类。"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Pattern, Protocol
from urllib.parse import unquote, urlparse

from app.provider_plugins.base.browser import BrowserDriver
from app.shared.errors import AppError

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Locator, Page, Response


class CamoufoxFactory(Protocol):
    """Camoufox 工厂协议。"""

    def __call__(self, **kwargs: object) -> Any:
        """创建 Camoufox 异步上下文管理器。"""


# 应放入 BrowserContext / persistent_context 的选项键.
_CONTEXT_OPTION_KEYS: frozenset[str] = frozenset(
    {
        "locale",
        "timezone_id",
        "user_agent",
        "viewport",
        "no_viewport",
        "geolocation",
        "permissions",
        "extra_http_headers",
        "ignore_https_errors",
        "java_script_enabled",
        "bypass_csp",
        "color_scheme",
        "reduced_motion",
        "forced_colors",
        "accept_downloads",
        "base_url",
        "offline",
        "http_credentials",
        "device_scale_factor",
        "is_mobile",
        "has_touch",
        "screen",
        "storage_state",
        "proxy",
        "record_har_path",
        "record_video_dir",
        "service_workers",
    }
)


class BaseCamoufox(BrowserDriver):
    """Camoufox 浏览器驱动实现。"""

    DEFAULT_TIMEOUT = 50
    """默认页面超时时间, 单位为秒。"""

    def __init__(self) -> None:
        """初始化浏览器运行状态。"""
        self._camoufox: Any | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._persistent_context = False
        self._default_timeout_ms = self.DEFAULT_TIMEOUT * 1000

    async def __aenter__(self) -> "BaseCamoufox":
        """作为异步上下文管理器进入 (需已调用 launch 或在外部 launch)。"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        """退出时关闭浏览器资源。"""
        del exc_type, exc, tb
        await self.close()

    @property
    def page(self) -> Page:
        """返回当前上下文中的最新页面。

        统一走 ``latest_page()``, 避免新标签打开后仍操作旧页.
        """
        return self.latest_page()

    def set_page(self, page: Page) -> None:
        """设置当前页面缓存。"""
        self._page = page
        page.set_default_timeout(self._default_timeout_ms)

    def latest_page(self) -> Page:
        """返回当前上下文中的最后一个页面。"""
        if self._context is not None:
            pages = list(self._context.pages)
            if pages:
                latest = pages[-1]
                self._page = latest
                return latest
        if self._page is not None:
            try:
                pages = list(self._page.context.pages)
            except Exception:
                return self._page
            if pages:
                latest = pages[-1]
                self._page = latest
                return latest
            return self._page
        raise AppError("Camoufox 页面未初始化, 请先调用 launch()")

    def set_default_timeout(self, timeout_ms: float) -> None:
        """设置后续页面操作的默认超时 (毫秒)。"""
        self._default_timeout_ms = max(0.0, float(timeout_ms))
        if self._page is not None:
            self._page.set_default_timeout(self._default_timeout_ms)
        if self._context is not None:
            for page in self._context.pages:
                page.set_default_timeout(self._default_timeout_ms)

    @staticmethod
    def _load_camoufox_class() -> CamoufoxFactory:
        """延迟导入 Camoufox 可选依赖。"""
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError as exc:
            raise AppError("未安装 camoufox 依赖, 请安装后再使用 BaseCamoufox") from exc
        return AsyncCamoufox

    @staticmethod
    def _parse_proxy(proxy: str) -> dict[str, str]:
        """解析代理地址, 支持 ``http://user:pass@host:port``。"""
        text = proxy.strip()
        if "://" not in text:
            text = f"http://{text}"
        parsed = urlparse(text)
        if not parsed.hostname:
            return {"server": proxy.strip()}
        port = f":{parsed.port}" if parsed.port else ""
        server = f"{parsed.scheme}://{parsed.hostname}{port}"
        result: dict[str, str] = {"server": server}
        if parsed.username:
            result["username"] = unquote(parsed.username)
        if parsed.password:
            result["password"] = unquote(parsed.password)
        return result

    @classmethod
    def _split_launch_and_context(
        cls,
        launch_options: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        """拆分浏览器启动参数与上下文参数。"""
        launch_args: dict[str, object] = {}
        context_args: dict[str, object] = {}
        for key, value in launch_options.items():
            if key in _CONTEXT_OPTION_KEYS:
                context_args[key] = value
            else:
                launch_args[key] = value
        return launch_args, context_args

    async def launch(
        self,
        headless: bool | Literal["virtual"] = False,
        proxy: str | None = None,
        user_data_dir: str | Path | None = None,
        context_options: dict[str, object] | None = None,
        **launch_options: object,
    ) -> Page:
        """启动 Camoufox 浏览器并创建页面。

        Args:
            headless: 无头模式. True 无头, False 有界面, ``"virtual"`` 使用虚拟显示.
            proxy: 代理地址, 支持带账号密码.
            user_data_dir: 持久化用户数据目录.
            context_options: 浏览器上下文额外选项.
            **launch_options: 透传给 Camoufox 的启动/上下文参数.
                ``locale`` / ``timezone_id`` 等会并入 context.
                默认 ``humanize=False``, 避免 Turnstile 鼠标操作被拖慢.
        """
        if self._camoufox is not None or self._page is not None:
            raise AppError("Camoufox 已启动, 请先 close() 再重新 launch()")

        camoufox_class = self._load_camoufox_class()
        extra_launch, extra_context = self._split_launch_and_context(dict(launch_options))

        # Camoufox virtual 会改写传入 env 的 DISPLAY, 必须隔离进程级环境.
        launch_env: dict[str, str] = dict(os.environ)
        custom_env = extra_launch.pop("env", None)
        if custom_env is not None:
            if not isinstance(custom_env, Mapping):
                raise AppError("Camoufox env 必须是键值映射")
            launch_env.update(
                {str(key): str(value) for key, value in custom_env.items()}
            )

        merged_launch_options: dict[str, object] = {
            "headless": headless,
            "env": launch_env,
            # humanize 会把 mouse.move 拖到数十秒, 默认关闭.
            # "humanize": False,
        }
        if proxy:
            merged_launch_options["proxy"] = self._parse_proxy(proxy)
        merged_launch_options.update(extra_launch)

        merged_context_options: dict[str, object] = {"no_viewport": True}
        merged_context_options.update(extra_context)
        if context_options:
            merged_context_options.update(context_options)
        # proxy 已在 launch 层设置时, context 不必重复; 若仅 context 需要可保留.
        if proxy and "proxy" not in merged_context_options:
            merged_context_options["proxy"] = self._parse_proxy(proxy)

        if user_data_dir is not None:
            # persistent_context 同时吃 launch + context 选项.
            merged_launch_options.update(merged_context_options)
            merged_launch_options["persistent_context"] = True
            merged_launch_options["user_data_dir"] = user_data_dir
            self._persistent_context = True
        else:
            # 非持久化: locale 等仅通过 new_context 生效.
            for key in list(merged_launch_options.keys()):
                if key in _CONTEXT_OPTION_KEYS and key not in {"proxy"}:
                    merged_context_options.setdefault(key, merged_launch_options.pop(key))

        self._camoufox = camoufox_class(**merged_launch_options)
        browser_or_context = await self._camoufox.__aenter__()
        # Browser 与 BrowserContext 都有 new_page; 用 pages 区分上下文对象.
        if hasattr(browser_or_context, "pages"):
            self._context = browser_or_context
        else:
            self._browser = browser_or_context
            # proxy 已在 browser 级设置时, 避免 new_context 再传一份冲突.
            context_kwargs = dict(merged_context_options)
            if "proxy" in merged_launch_options:
                context_kwargs.pop("proxy", None)
            self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._default_timeout_ms)
        return self._page

    async def close(self) -> None:
        """关闭 Camoufox 相关资源, 分段尽量释放且不向外抛错 (供 finally 使用)。"""
        if self._page is not None and not self._persistent_context:
            try:
                await self._page.close()
            except Exception:
                pass
        self._page = None

        if self._context is not None and not self._persistent_context:
            try:
                await self._context.close()
            except Exception:
                pass
        self._context = None

        if self._camoufox is not None:
            try:
                await self._camoufox.__aexit__(None, None, None)
            except Exception:
                pass
        self._camoufox = None
        self._browser = None
        self._persistent_context = False

    async def click_and_wait_for_page(
        self,
        locator: Locator,
        timeout: float | None = None,
    ) -> Page:
        """点击目标元素并等待新标签页。"""
        if self._context is None:
            raise AppError("Camoufox 上下文未初始化, 请先调用 launch()")

        async with self._context.expect_page() as new_page_info:
            await locator.click(timeout=timeout, force=True)
        new_page = await new_page_info.value
        self.set_page(new_page)
        return new_page

    async def evaluate(self, script: str, arg: object | None = None) -> Any:
        """在最新页面上下文执行 JavaScript。"""
        page = self.latest_page()
        if arg is None:
            return await page.evaluate(script)
        return await page.evaluate(script, arg)

    async def screenshot(self, path: str, full_page: bool = False) -> bytes:
        """保存页面截图, 默认仅视口 (失败排查更快)。"""
        return await self.latest_page().screenshot(
            path=path,
            full_page=full_page,
            type="png",
        )

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
        page = self.latest_page()
        cookies = await page.context.cookies(page.url)
        return self.filter_valid_cookies(cookies)

    async def has_cookie(self, name: str) -> bool:
        """按名称模糊匹配判断指定 Cookie 是否存在。"""
        cookies = await self.get_cookies()
        return any(name in str(cookie.get("name", "")) for cookie in cookies)

    async def goto(
        self,
        url: str,
        wait_until: Literal[
            "commit",
            "domcontentloaded",
            "load",
            "networkidle",
        ] = "domcontentloaded",
        *,
        timeout: float | None = None,
    ) -> Response | None:
        """在最新页面跳转到指定地址。"""
        kwargs: dict[str, object] = {"wait_until": wait_until}
        if timeout is not None:
            kwargs["timeout"] = timeout
        return await self.latest_page().goto(url, **kwargs)

    def current_url(self) -> str:
        """返回最新页面 URL。"""
        return str(self.latest_page().url)

    async def title(self) -> str:
        """返回最新页面标题。"""
        return str(await self.latest_page().title())

    async def wait_for_timeout(self, timeout_ms: float) -> None:
        """等待指定毫秒数。"""
        await self.latest_page().wait_for_timeout(timeout_ms)

    async def wait_for_load_state(
        self,
        state: Literal["domcontentloaded", "load", "networkidle"] = "networkidle",
        *,
        timeout: float | None = None,
    ) -> None:
        """等待最新页面达到指定加载状态。"""
        kwargs: dict[str, object] = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await self.latest_page().wait_for_load_state(state, **kwargs)

    async def wait_for_url(
        self,
        url: str | Pattern[str] | Callable[[str], bool],
        *,
        wait_until: Literal[
            "commit",
            "domcontentloaded",
            "load",
            "networkidle",
        ]
        | None = None,
        timeout: float | None = None,
    ) -> None:
        """等待最新页面 URL 匹配指定条件。

        Args:
            url: 目标 URL 字符串, 正则, 或 ``(url: str) -> bool`` 判定函数.
            wait_until: 匹配后额外等待的加载状态, 可选.
            timeout: 最长等待毫秒数; ``None`` 使用页面默认超时.
        """
        await self.latest_page().wait_for_url(
            url,
            wait_until=wait_until,
            timeout=timeout,
        )

    def locator(self, selector: str) -> Locator:
        """按 CSS/文本选择器在最新页面创建定位器。"""
        return self.latest_page().locator(selector)
