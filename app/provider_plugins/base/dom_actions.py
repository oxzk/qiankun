"""浏览器 DOM 等待与操作辅助。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from app.provider_plugins.base.browser import BrowserDriver
from app.shared.errors import AppError

if TYPE_CHECKING:
    from playwright.async_api import Locator

T = TypeVar("T")


class DomActionsMixin:
    """为 ``BaseBrowserProvider`` 提供选择器等待与操作。

    依赖宿主提供 ``ELEMENT_POLL_MS`` 与 ``log``.
    """

    ELEMENT_POLL_MS: int
    log: Callable[..., None]

    async def wait_for_any_selector(
        self,
        browser: BrowserDriver,
        selectors: tuple[str, ...],
        *,
        timeout_ms: int,
    ) -> Locator | None:
        """等待任一 CSS 选择器可见, 返回命中元素的 Locator; 超时返回 None。"""
        import time

        if not selectors:
            return None
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            for selector in selectors:
                locator = browser.locator(selector).first
                try:
                    if await locator.count() > 0 and await locator.is_visible():
                        return locator
                except Exception:
                    continue
            remaining_ms = max(0.0, (deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            await browser.wait_for_timeout(min(self.ELEMENT_POLL_MS, remaining_ms))
        for selector in selectors:
            locator = browser.locator(selector).first
            try:
                if await locator.count() > 0 and await locator.is_visible():
                    return locator
            except Exception:
                continue
        return None

    async def wait_for_selector(
        self,
        browser: BrowserDriver,
        selector: str,
        *,
        timeout_ms: int,
        state: str = "visible",
    ) -> Locator | None:
        """等待选择器达到指定状态, 成功返回 Locator, 超时返回 None。"""
        locator = browser.locator(selector).first
        try:
            await locator.wait_for(
                state=state,  # type: ignore[attr-defined]
                timeout=timeout_ms,
            )
            return locator
        except Exception:
            return None

    async def _wait_for_selector_action(
        self,
        browser: BrowserDriver,
        selector: str,
        *,
        timeout_ms: int,
        state: str,
        action_name: str,
        action: Callable[[Locator], Awaitable[T]],
    ) -> tuple[Locator, T]:
        """等待选择器后执行动作; 找不到元素或动作失败时抛出 ``AppError``。"""
        locator = await self.wait_for_selector(
            browser,
            selector,
            timeout_ms=timeout_ms,
            state=state,
        )
        if locator is None:
            raise AppError(f"未找到元素: {selector}")
        try:
            result = await action(locator)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                f"{action_name}失败 {selector}: {type(exc).__name__}: {exc}"
            ) from exc
        return locator, result

    async def wait_for_selector_click(
        self,
        browser: BrowserDriver,
        selector: str,
        *,
        timeout_ms: int,
        state: str = "visible",
        click_timeout_ms: int | None = None,
        force: bool = False,
    ) -> Locator:
        """等待选择器可见后点击, 失败抛出 ``AppError``。"""
        action_timeout = click_timeout_ms if click_timeout_ms is not None else timeout_ms

        async def _click(locator: Locator) -> None:
            await locator.click(timeout=action_timeout, force=force)

        locator, _ = await self._wait_for_selector_action(
            browser,
            selector,
            timeout_ms=timeout_ms,
            state=state,
            action_name="点击",
            action=_click,
        )
        return locator

    async def wait_for_selector_fill(
        self,
        browser: BrowserDriver,
        selector: str,
        value: str,
        *,
        timeout_ms: int,
        state: str = "visible",
        fill_timeout_ms: int | None = None,
    ) -> Locator:
        """等待选择器可见后填入文本, 失败抛出 ``AppError``。"""
        action_timeout = fill_timeout_ms if fill_timeout_ms is not None else timeout_ms

        async def _fill(locator: Locator) -> None:
            await locator.fill(value, timeout=action_timeout)

        locator, _ = await self._wait_for_selector_action(
            browser,
            selector,
            timeout_ms=timeout_ms,
            state=state,
            action_name="填写",
            action=_fill,
        )
        return locator

    async def wait_for_selector_text(
        self,
        browser: BrowserDriver,
        selector: str,
        *,
        timeout_ms: int,
        state: str = "visible",
    ) -> str:
        """等待选择器可见后读取 inner_text, 失败抛出 ``AppError``。"""

        async def _text(locator: Locator) -> str:
            text = await locator.inner_text(timeout=timeout_ms)
            return str(text or "").strip()

        _, text = await self._wait_for_selector_action(
            browser,
            selector,
            timeout_ms=timeout_ms,
            state=state,
            action_name="读取文本",
            action=_text,
        )
        return text

    async def wait_for_selector_check(
        self,
        browser: BrowserDriver,
        selector: str,
        *,
        timeout_ms: int,
        state: str = "visible",
        checked: bool = True,
        check_timeout_ms: int | None = None,
    ) -> Locator:
        """等待选择器可见后勾选/取消勾选, 失败抛出 ``AppError``。"""
        action_timeout = check_timeout_ms if check_timeout_ms is not None else timeout_ms

        async def _check(locator: Locator) -> None:
            if checked:
                await locator.check(timeout=action_timeout)
            else:
                await locator.uncheck(timeout=action_timeout)

        locator, _ = await self._wait_for_selector_action(
            browser,
            selector,
            timeout_ms=timeout_ms,
            state=state,
            action_name="勾选" if checked else "取消勾选",
            action=_check,
        )
        return locator

    async def is_selector_visible(self, browser: BrowserDriver, selector: str) -> bool:
        """判断选择器对应首个元素是否可见。"""
        try:
            locator = browser.locator(selector).first
            count = await locator.count()
            if count <= 0:
                return False
            return bool(await locator.is_visible())
        except Exception:
            return False
