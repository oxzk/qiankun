"""浏览器运行环境隔离与异常处理测试。"""

from __future__ import annotations

import os
from typing import Any, ClassVar, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from app.provider_plugins.base.browser import BrowserDriver
from app.provider_plugins.base.browser_provider import BaseBrowserProvider
from app.provider_plugins.base.camoufox import BaseCamoufox
from app.provider_plugins.contracts import BrowserProviderConfig, ProviderResult
from app.shared.errors import AppError


class _FakePage:
    """模拟 Playwright 页面。"""

    def __init__(self, context: "_FakeBrowserContext") -> None:
        """绑定页面所属上下文。"""
        self.context = context
        self.default_timeout_ms = 0.0

    def set_default_timeout(self, timeout_ms: float) -> None:
        """记录默认超时时间。"""
        self.default_timeout_ms = timeout_ms

    async def close(self) -> None:
        """模拟关闭页面。"""


class _FakeBrowserContext:
    """模拟 Playwright 浏览器上下文。"""

    def __init__(self) -> None:
        """初始化页面集合。"""
        self.pages: list[_FakePage] = []

    async def new_page(self) -> _FakePage:
        """创建并记录模拟页面。"""
        page = _FakePage(self)
        self.pages.append(page)
        return page

    async def close(self) -> None:
        """模拟关闭浏览器上下文。"""


class _FakeBrowser:
    """模拟 Playwright 浏览器。"""

    async def new_context(self, **kwargs: object) -> _FakeBrowserContext:
        """创建模拟浏览器上下文。"""
        del kwargs
        return _FakeBrowserContext()


class _FakeCamoufoxContext:
    """模拟会在 virtual 模式改写启动环境的 Camoufox。"""

    launches: ClassVar[list[dict[str, object]]] = []

    def __init__(self, **options: object) -> None:
        """记录单次 Camoufox 启动参数。"""
        self.options = options
        self.launches.append(options)

    async def __aenter__(self) -> _FakeBrowser:
        """模拟 Camoufox 创建浏览器。"""
        environment = self.options["env"]
        if not isinstance(environment, dict):
            raise TypeError("测试启动环境必须是 dict")
        if self.options["headless"] == "virtual":
            environment["DISPLAY"] = ":0"
        return _FakeBrowser()

    async def __aexit__(self, *args: Any) -> None:
        """模拟关闭 Camoufox。"""
        del args


class _TestBrowserProvider(BaseBrowserProvider):
    """用于验证浏览器异常处理的 Provider。"""

    name = "browser-runtime-test"

    async def execute_with_browser(
        self,
        browser: BrowserDriver,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """返回固定成功结果。"""
        del browser, provider_config
        return ProviderResult.ok()


class BaseCamoufoxEnvironmentTests(IsolatedAsyncioTestCase):
    """验证 false 与 virtual 的启动环境相互隔离。"""

    async def asyncSetUp(self) -> None:
        """清理模拟启动记录。"""
        _FakeCamoufoxContext.launches.clear()

    async def test_virtual_does_not_pollute_following_false_launch(self) -> None:
        """验证 virtual 改写私有环境后 false 仍继承容器显示器。"""
        with (
            patch.dict(os.environ, {"DISPLAY": ":99"}),
            patch.object(
                BaseCamoufox,
                "_load_camoufox_class",
                return_value=_FakeCamoufoxContext,
            ),
        ):
            virtual_browser = BaseCamoufox()
            await virtual_browser.launch(headless="virtual")
            await virtual_browser.close()

            self.assertEqual(os.environ["DISPLAY"], ":99")

            visible_browser = BaseCamoufox()
            await visible_browser.launch(headless=False)
            await visible_browser.close()

        self.assertEqual(len(_FakeCamoufoxContext.launches), 2)
        virtual_env = cast(dict[str, str], _FakeCamoufoxContext.launches[0]["env"])
        visible_env = cast(dict[str, str], _FakeCamoufoxContext.launches[1]["env"])
        self.assertIsNot(virtual_env, visible_env)
        self.assertEqual(virtual_env["DISPLAY"], ":0")
        self.assertEqual(visible_env["DISPLAY"], ":99")

    async def test_custom_environment_merges_into_private_copy(self) -> None:
        """验证自定义环境合并后仍不修改进程级环境。"""
        with (
            patch.dict(os.environ, {"DISPLAY": ":99", "LANG": "C"}),
            patch.object(
                BaseCamoufox,
                "_load_camoufox_class",
                return_value=_FakeCamoufoxContext,
            ),
        ):
            browser = BaseCamoufox()
            await browser.launch(headless=False, env={"LANG": "zh_CN.UTF-8"})
            await browser.close()

            self.assertEqual(os.environ["LANG"], "C")

        launch_env = cast(dict[str, str], _FakeCamoufoxContext.launches[0]["env"])
        self.assertEqual(launch_env["DISPLAY"], ":99")
        self.assertEqual(launch_env["LANG"], "zh_CN.UTF-8")


class BrowserExceptionTests(IsolatedAsyncioTestCase):
    """验证浏览器启动阶段异常不会触发截图。"""

    async def test_launch_failure_skips_screenshot_without_page(self) -> None:
        """验证页面未初始化时直接返回失败结果。"""
        provider = _TestBrowserProvider()
        browser = Mock(spec=BrowserDriver)
        browser.latest_page.side_effect = AppError("页面未初始化")
        browser.screenshot = AsyncMock()

        result = await provider.handle_browser_exception(
            browser=browser,
            exc=RuntimeError("launch failed"),
            provider_config=BrowserProviderConfig(),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.data, {"error": "launch failed"})
        browser.screenshot.assert_not_awaited()
