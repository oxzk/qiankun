"""浏览器驱动抽象。

后续可在此扩展 Playwright / Selenium 等实现, Provider 只依赖本协议.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from re import Pattern
from typing import Any, Literal


class BrowserDriver(ABC):
    """浏览器驱动通用基类。

    ``BaseBrowserProvider`` 与业务 Provider 仅依赖本抽象,
    具体引擎 (如 Camoufox) 通过子类接入.

    本抽象只覆盖引擎原语 (启动/导航/定位/求值/截图).
    Cloudflare Turnstile 等站点验证能力属于 Provider 编排层,
    见 ``BaseBrowserProvider.handle_visible_turnstile``, 不在此契约内.
    """

    @abstractmethod
    async def launch(
        self,
        headless: bool | Literal["virtual"] = False,
        proxy: str | None = None,
        user_data_dir: str | Path | None = None,
        context_options: dict[str, object] | None = None,
        **launch_options: object,
    ) -> Any:
        """启动浏览器并返回初始页面对象。"""

    @abstractmethod
    async def close(self) -> None:
        """关闭浏览器及相关资源。"""

    @abstractmethod
    def latest_page(self) -> Any:
        """返回当前上下文中的最新页面。"""

    @abstractmethod
    def current_url(self) -> str:
        """返回最新页面 URL。"""

    @abstractmethod
    async def title(self) -> str:
        """返回最新页面标题。"""

    @abstractmethod
    async def screenshot(self, path: str, full_page: bool = False) -> bytes:
        """保存截图到指定路径, 返回二进制内容。"""

    @abstractmethod
    async def evaluate(self, script: str, arg: object | None = None) -> Any:
        """在最新页面执行 JavaScript。"""

    @abstractmethod
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
    ) -> Any:
        """导航到指定 URL。"""

    @abstractmethod
    async def wait_for_timeout(self, timeout_ms: float) -> None:
        """等待指定毫秒数。"""

    @abstractmethod
    async def wait_for_load_state(
        self,
        state: Literal["domcontentloaded", "load", "networkidle"] = "networkidle",
        *,
        timeout: float | None = None,
    ) -> None:
        """等待页面达到指定加载状态。"""

    @abstractmethod
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
        """等待 URL 匹配指定条件。"""

    @abstractmethod
    def locator(self, selector: str) -> Any:
        """按选择器创建页面定位器。"""
