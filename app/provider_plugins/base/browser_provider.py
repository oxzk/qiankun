"""浏览器 Provider 执行基类。"""

from __future__ import annotations

import shutil
from abc import abstractmethod
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from app.provider_plugins.base.browser import BrowserDriver
from app.provider_plugins.base.camoufox import BaseCamoufox
from app.provider_plugins.base.dom_actions import DomActionsMixin
from app.provider_plugins.base.provider import BaseProvider
from app.provider_plugins.base.turnstile import TurnstileDetector, TurnstileHandler, TurnstileSnapshot
from app.provider_plugins.contracts import (
    BrowserProviderConfig,
    ProviderConfig,
    ProviderResult,
)

BrowserFactory = Callable[[], BrowserDriver]
"""浏览器驱动工厂类型, 默认生产 ``BaseCamoufox``。"""


class BaseBrowserProvider(DomActionsMixin, BaseProvider):
    """浏览器 Provider 基类。

    封装 ``BrowserDriver`` 启动/关闭、Turnstile 处理、DOM 等待与失败截图.
    配置校验由 ``BaseProvider.run`` 完成; 子类实现 ``execute_with_browser``.
    """

    config_schema: ClassVar[type[BrowserProviderConfig]] = BrowserProviderConfig
    launch_options: ClassVar[dict[str, object]] = {}
    default_wait_load_state: ClassVar[str | None] = "load"
    screenshot_keep: ClassVar[int] = 20
    ELEMENT_POLL_MS: ClassVar[int] = 300

    def __init__(
        self,
        requester: object | None = None,
        browser_factory: BrowserFactory | None = None,
    ) -> None:
        """初始化浏览器 Provider。"""
        super().__init__(requester=requester)  # type: ignore[arg-type]
        self._browser_factory: BrowserFactory = browser_factory or BaseCamoufox

    @property
    def data_dir(self) -> Path:
        """当前 Provider 数据根目录。"""
        return Path("data") / "providers" / self.name

    @property
    def screenshot_dir(self) -> Path:
        """当前 Provider 截图目录。"""
        return self.data_dir / "screenshots"

    async def execute(self, config: ProviderConfig) -> ProviderResult:
        """启动浏览器并执行子类业务流程 (config 已校验)。"""
        provider_config = config if isinstance(config, BrowserProviderConfig) else self.config_schema.model_validate(config)
        self._rotate_screenshots()
        browser = self._browser_factory()
        try:
            headless = provider_config.resolve_headless()
            self.log(
                "启动浏览器: "
                f"target={self._format_browser_target(provider_config)}, "
                f"headless={provider_config.headless}, "
                f"user_data_dir={provider_config.user_data_dir or '禁用'}"
            )
            await browser.launch(
                headless=headless,
                proxy=provider_config.proxy,
                user_data_dir=provider_config.user_data_dir,
                **dict(self.launch_options),
            )
            return await self.execute_with_browser(
                browser=browser,
                provider_config=provider_config,
            )
        except Exception as exc:
            return await self.handle_browser_exception(
                browser=browser,
                exc=exc,
                provider_config=provider_config,
            )
        finally:
            await browser.close()

    @abstractmethod
    async def execute_with_browser(
        self,
        browser: BrowserDriver,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """执行子类浏览器业务流程。"""

    async def handle_browser_exception(
        self,
        browser: BrowserDriver,
        exc: Exception,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """处理浏览器业务异常, 并尝试保存失败截图。"""
        del provider_config
        message = f"{self.name} 浏览器任务执行失败: {type(exc).__name__}"
        self.log(f"{message}: {exc}")
        data: dict[str, object] = {"error": str(exc)}
        try:
            data["title"] = await browser.title()
            self.log(f"失败页标题: {data['title']}", log_type="system")
        except Exception:
            pass
        return await self.fail_with_screenshot(
            browser,
            message=message,
            reason="browser_error",
            data=data,
        )

    async def fail_with_screenshot(
        self,
        browser: BrowserDriver,
        *,
        message: str,
        reason: str,
        data: dict[str, object] | None = None,
    ) -> ProviderResult:
        """构造失败结果并附带截图路径与当前 URL。"""
        payload: dict[str, object] = dict(data or {})
        try:
            payload.setdefault("url", browser.current_url())
        except Exception:
            pass
        screenshot = await self.save_screenshot(browser, reason=reason)
        if screenshot:
            payload["screenshot"] = screenshot
        return ProviderResult.fail(message=message, data=payload)

    async def save_screenshot(
        self,
        browser: BrowserDriver,
        reason: str,
        prefix: str | None = None,
        *,
        full_page: bool = False,
    ) -> str:
        """保存当前页面截图, 失败时返回空字符串。"""
        try:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_prefix = prefix or self.name
            path = self.screenshot_dir / f"{file_prefix}_{reason}_{timestamp}.png"
            await browser.screenshot(str(path), full_page=full_page)
            self.log(f"已保存截图: {path}", log_type="system")
            self._rotate_screenshots()
            return str(path)
        except Exception as exc:
            self.log(f"保存截图失败: {exc}", log_type="system")
            return ""

    def _turnstile_log(self, message: object, *args: object, **kwargs: object) -> None:
        """Turnstile 底层细节以系统日志输出。"""
        del args, kwargs
        self.log(message if isinstance(message, str) else str(message), log_type="system")

    async def detect_turnstile(self, browser: BrowserDriver) -> TurnstileSnapshot:
        """检测 Turnstile 并记录快照日志。"""
        detector = TurnstileDetector(browser.latest_page(), log_func=self._turnstile_log)
        snapshot = await detector.detect()
        rect = snapshot.rect
        rect_text = (
            f"({rect['x']:.0f},{rect['y']:.0f},{rect['width']:.0f}x{rect['height']:.0f})"
            if rect is not None
            else "None"
        )
        self.log(
            "Turnstile 检测结果: "
            f"present={snapshot.present}, visible={snapshot.visible}, "
            f"rect={rect_text}, source={snapshot.source}, "
            f"target_kind={snapshot.target_kind}",
            log_type="system",
        )
        return snapshot

    async def is_turnstile_visible(self, browser: BrowserDriver) -> bool:
        """检测页面是否存在可见 Turnstile。"""
        try:
            snapshot = await self.detect_turnstile(browser)
        except Exception as exc:
            self.log(f"Turnstile 检测异常: {exc}", log_type="system")
            return False
        return snapshot.visible or snapshot.rect is not None

    async def handle_visible_turnstile(
        self,
        browser: BrowserDriver,
        *,
        timeout: float = 45.0,
        click_interval: float = 10.0,
        max_clicks: int = 5,
    ) -> bool:
        """处理页面 Turnstile (唯一对外入口)。"""
        page = browser.latest_page()
        detector = TurnstileDetector(page, log_func=self._turnstile_log)
        handler = TurnstileHandler(page, detector, log_func=self._turnstile_log)
        try:
            handled = await handler.handle(
                timeout=timeout,
                click_interval=click_interval,
                max_clicks=max_clicks,
            )
        except Exception as exc:
            self.log(f"Turnstile 处理异常: {exc}", log_type="system")
            self.log("Turnstile 处理异常")
            return False

        if handled:
            self.log("Turnstile 验证已完成")
            return True
        self.log("Turnstile 验证未通过")
        return False

    async def open_url(
        self,
        browser: BrowserDriver,
        url: str,
        *,
        wait_until: str = "domcontentloaded",
        wait_load_state: str | None | object = ...,
        load_state_timeout_ms: float | None = 25_000,
    ) -> None:
        """打开指定地址并等待页面加载完成。"""
        state: str | None
        if wait_load_state is ...:
            state = self.default_wait_load_state
        else:
            state = wait_load_state  # type: ignore[assignment]

        self.log(f"打开页面: {url}")
        await browser.goto(url, wait_until=wait_until)
        if not state:
            return
        try:
            await browser.wait_for_load_state(
                state,  # type: ignore[arg-type]
                timeout=load_state_timeout_ms,
            )
        except Exception as exc:
            self.log(
                f"wait_for_load_state({state}) 未完成: "
                f"{type(exc).__name__}: {exc}",
                log_type="system",
            )

    async def refresh_page(self, browser: BrowserDriver) -> bool:
        """使用 ``open_url`` 刷新当前页面, 返回是否刷新成功。"""
        try:
            await self.open_url(browser, browser.current_url())
            return True
        except Exception as exc:
            self.log(f"刷新页面失败: {type(exc).__name__}: {exc}")
            return False

    async def open_url_and_check(
        self,
        browser: BrowserDriver,
        url: str,
        keyword: str | Sequence[str],
        *,
        wait_until: str = "domcontentloaded",
        wait_load_state: str | None | object = ...,
        timeout_ms: int = 15_000,
        case_insensitive: bool = True,
    ) -> bool:
        """打开地址并等待 URL 命中任一关键词, 返回是否命中。

        ``keyword`` 可传多个落地关键词 (如 login 与 daily-checkin),
        任一命中即结束等待, 避免已登录场景空等超时.
        """
        await self.open_url(
            browser,
            url,
            wait_until=wait_until,
            wait_load_state=wait_load_state,
        )

        def _norm(text: str) -> str:
            return text.lower() if case_insensitive else text

        if isinstance(keyword, str):
            raw_keywords: Sequence[str] = (keyword,)
        else:
            raw_keywords = keyword
        needles = [_norm(item) for item in raw_keywords if str(item).strip()]
        if not needles:
            self.log("URL 检查: 未提供有效 keyword", log_type="system")
            return False

        def _matched_any(current: str) -> bool:
            haystack = _norm(current)
            return any(needle in haystack for needle in needles)

        current = browser.current_url()
        if not _matched_any(current):
            try:
                await browser.wait_for_url(_matched_any, timeout=timeout_ms)
            except Exception as exc:
                if type(exc).__name__ not in {"TimeoutError", "Error", "TargetClosedError"}:
                    self.log(
                        f"wait_for_url 异常: {type(exc).__name__}: {exc}",
                        log_type="system",
                    )
            current = browser.current_url()

        matched = _matched_any(current)
        self.log(
            f"URL 检查: keywords={list(needles)!r}, matched={matched}, url={current}",
            log_type="system",
        )
        return matched

    def _rotate_screenshots(self) -> None:
        """按 mtime 仅保留最近 ``screenshot_keep`` 张截图。"""
        screenshot_dir = self.screenshot_dir
        if not screenshot_dir.exists():
            return
        keep = max(0, int(self.screenshot_keep))
        files = [
            path
            for path in screenshot_dir.iterdir()
            if path.is_file() and not path.is_symlink()
        ]
        if keep <= 0:
            for path in files:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    self.log(f"清理截图失败: {path}: {exc}", log_type="system")
            return
        if len(files) <= keep:
            return
        files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files[keep:]:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                self.log(f"清理截图失败: {path}: {exc}", log_type="system")
        for child in screenshot_dir.iterdir():
            if child.is_dir() and not child.is_symlink():
                try:
                    shutil.rmtree(child)
                except OSError as exc:
                    self.log(f"清理截图目录失败: {child}: {exc}", log_type="system")

    def _format_browser_target(self, provider_config: BrowserProviderConfig) -> str:
        """格式化浏览器启动日志中的目标地址。"""
        for field_name in ("url", "base_url", "checkin_url"):
            value = getattr(provider_config, field_name, None)
            if value:
                return str(value)
        return self.name
