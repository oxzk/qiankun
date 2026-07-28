"""浏览器 Provider 执行基类。"""

from __future__ import annotations

import shutil
import time
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from pydantic import ValidationError

from app.provider_plugins.base.camoufox import BaseCamoufox
from app.provider_plugins.base.provider import BaseProvider
from app.provider_plugins.base.turnstile import TurnstileDetector, TurnstileHandler
from app.provider_plugins.contracts import (
    BrowserProviderConfig,
    ProviderConfig,
    ProviderResult,
)


class BaseBrowserProvider(BaseProvider):
    """浏览器 Provider 基类。

    封装配置校验、Camoufox 启动/关闭、Turnstile 处理、
    通用 DOM 等待与失败截图。子类实现 ``execute_with_browser`` 即可。
    """

    config_schema: ClassVar[type[BrowserProviderConfig]] = BrowserProviderConfig
    launch_options: ClassVar[dict[str, object]] = {}
    CHECK_IN_SUCCESS: ClassVar[str] = "签到成功"
    CHECK_IN_ALREADY_DONE: ClassVar[str] = "今日已签到"
    CHECK_IN_NOT_FOUND: ClassVar[str] = "未找到签到按钮"
    ELEMENT_POLL_MS: ClassVar[int] = 300

    @property
    def data_dir(self) -> Path:
        """当前 Provider 数据根目录。"""
        return Path("data") / "providers" / self.name

    @property
    def screenshot_dir(self) -> Path:
        """当前 Provider 截图目录。"""
        return self.data_dir / "screenshots"

    async def execute(self, config: ProviderConfig) -> ProviderResult:
        """校验配置、启动浏览器并执行子类业务流程。"""
        try:
            provider_config = self.config_schema.model_validate(config)
        except ValidationError as exc:
            message = self._format_config_error(exc)
            self.log(message)
            return ProviderResult.fail(
                message=message,
                data={"error": type(exc).__name__},
            )

        self._clean_screenshot_dir()
        browser = BaseCamoufox()
        try:
            self.log(
                "启动 Camoufox: "
                f"target={self._format_browser_target(provider_config)}, "
                f"headless={provider_config.headless}, "
                f"user_data_dir={provider_config.user_data_dir or '禁用'}"
            )
            await browser.launch(
                headless=provider_config.headless,
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
        browser: BaseCamoufox,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """执行子类浏览器业务流程。"""

    async def handle_browser_exception(
        self,
        browser: BaseCamoufox,
        exc: Exception,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """处理浏览器业务异常, 并尝试保存失败截图。"""
        del provider_config  # 预留扩展点, 子类可覆盖使用。
        message = f"{self.name} 浏览器任务执行失败: {type(exc).__name__}"
        self.log(f"{message}: {exc}")
        data: dict[str, object] = {"error": str(exc)}
        try:
            data["url"] = browser.current_url()
        except Exception:
            pass
        try:
            data["title"] = await browser.title()
            self.log(f"页面标题: {data['title']}")
        except Exception:
            pass
        screenshot = await self.save_screenshot(browser, reason="browser_error")
        if screenshot:
            data["screenshot"] = screenshot
        return ProviderResult.fail(message=message, data=data)

    async def fail_with_screenshot(
        self,
        browser: BaseCamoufox,
        *,
        message: str,
        reason: str,
        data: dict[str, object] | None = None,
    ) -> ProviderResult:
        """构造失败结果并附带截图路径。"""
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
        browser: BaseCamoufox,
        reason: str,
        prefix: str | None = None,
    ) -> str:
        """保存当前页面截图, 失败时返回空字符串。"""
        try:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_prefix = prefix or self.name
            path = self.screenshot_dir / f"{file_prefix}_{reason}_{timestamp}.png"
            await browser.screenshot(str(path))
            self.log(f"已保存截图: {path}")
            return str(path)
        except Exception as exc:
            self.log(f"保存截图失败: {exc}")
            return ""

    async def is_turnstile_visible(self, browser: BaseCamoufox) -> bool:
        """检测页面是否存在可见 Turnstile。"""
        detector = TurnstileDetector(browser.latest_page(), log_func=self.log)
        try:
            snapshot = await detector.detect()
        except Exception as exc:
            self.log(f"Turnstile 检测异常: {exc}")
            return False
        return snapshot.visible

    async def handle_visible_turnstile(self, browser: BaseCamoufox) -> bool:
        """仅在 Turnstile 可见时处理验证。"""
        page = browser.latest_page()
        detector = TurnstileDetector(page, log_func=self.log)
        try:
            snapshot = await detector.detect()
        except Exception as exc:
            self.log(f"Turnstile 检测异常, 跳过处理: {exc}")
            return False

        if not snapshot.visible:
            self.log("Turnstile 未显示, 跳过处理")
            return False

        self.log(
            "检测到可见 Turnstile, "
            f"target={snapshot.target_kind}, source={snapshot.source}"
        )
        handler = TurnstileHandler(page, detector)
        try:
            handled = await handler.handle()
        except Exception as exc:
            self.log(f"Turnstile 处理异常: {exc}")
            return False

        if handled:
            self.log("Turnstile 验证已完成")
            return True
        self.log("Turnstile 验证未通过")
        return False

    async def wait_for_any_selector(
        self,
        browser: BaseCamoufox,
        selectors: tuple[str, ...],
        *,
        timeout_ms: int,
    ) -> bool:
        """轮询等待任一选择器可见。"""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            for selector in selectors:
                if await self.is_selector_visible(browser, selector):
                    return True
            await browser.wait_for_timeout(self.ELEMENT_POLL_MS)
        for selector in selectors:
            if await self.is_selector_visible(browser, selector):
                return True
        return False

    async def is_selector_visible(self, browser: BaseCamoufox, selector: str) -> bool:
        """判断选择器对应首个元素是否可见。"""
        try:
            locator = browser.locator(selector).first
            count = await locator.count()
            if count <= 0:
                return False
            return bool(await locator.is_visible())
        except Exception:
            return False

    def _clean_screenshot_dir(self) -> None:
        """清理当前 Provider 历史截图, 避免干扰本次排查。"""
        screenshot_dir = self.screenshot_dir
        if not screenshot_dir.exists():
            return
        for child in screenshot_dir.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            except OSError as exc:
                self.log(f"清理截图失败: {child}: {exc}")
        self.log(f"已清理截图目录: {screenshot_dir}")

    def _format_browser_target(self, provider_config: BrowserProviderConfig) -> str:
        """格式化浏览器启动日志中的目标地址。"""
        for field_name in ("url", "base_url", "checkin_url"):
            value = getattr(provider_config, field_name, None)
            if value:
                return str(value)
        return self.name

    def _format_config_error(self, exc: ValidationError) -> str:
        """格式化配置校验错误。"""
        first_error = exc.errors()[0] if exc.errors() else {}
        message = str(first_error.get("msg") or exc)
        return f"{self.name} 配置错误: {message}"
