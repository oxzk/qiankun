"""Cloudflare Turnstile 容器检测与全局鼠标处理。"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnstileSnapshot:
    """Turnstile 检测快照。

    Attributes:
        present: 页面是否存在 Turnstile 特征。
        visible: 是否存在位于当前视口的可见组件。
        rect: 组件在页面视口中的矩形。
        source: 几何信息来源。
        target_kind: 命中的组件类型。
        token: 检测到的响应令牌。
    """

    present: bool = False
    visible: bool = False
    rect: dict[str, float] | None = None
    source: str = "dom"
    target_kind: str = "none"
    token: str = ""


class TurnstileDetector:
    """使用页面容器几何检测 Turnstile。"""

    TOKEN_SELECTOR = (
        'input[name="cf-turnstile-response"], '
        'textarea[name="cf-turnstile-response"]'
    )
    CONTAINER_SELECTORS = (
        ".cf-turnstile",
        ".turnstile-wrapper",
        ".turnstile-container",
        "[class*='turnstile']",
        "[data-sitekey]",
        "[id*='turnstile']",
        "[id^='cf-chl']",
    )

    def __init__(
        self,
        page: Any,
        log_func: Callable[..., None] | None = None,
    ) -> None:
        """创建 Turnstile 检测器。"""
        self.page = page
        self.log = log_func or (lambda *args, **kwargs: None)

    async def detect(self) -> TurnstileSnapshot:
        """检测 Turnstile 容器、iframe 和可见矩形。"""
        try:
            raw = await self.page.evaluate(self._DETECT_SCRIPT) or {}
        except Exception as exc:
            self.log(f"Turnstile 容器检测失败: {exc}")
            return TurnstileSnapshot()
        rect = self._normalize_rect(raw.get("rect"))
        return TurnstileSnapshot(
            present=bool(raw.get("present")),
            visible=bool(raw.get("visible")) and rect is not None,
            rect=rect,
            source=str(raw.get("source") or "dom"),
            target_kind=str(raw.get("target_kind") or "none"),
        )

    async def is_visible(self) -> bool:
        """返回页面上是否显示 Turnstile。"""
        return (await self.detect()).visible

    async def get_token(self) -> str:
        """读取页面中的 Turnstile 响应令牌。"""
        try:
            value = await self.page.evaluate(
                """selector => {
                    const values = [];
                    for (const el of document.querySelectorAll(selector)) {
                        if (el && el.value) values.push(String(el.value));
                    }
                    return values.find(Boolean) || "";
                }""",
                self.TOKEN_SELECTOR,
            )
        except Exception:
            return ""
        return str(value or "").strip()

    @staticmethod
    def _normalize_rect(raw: object) -> dict[str, float] | None:
        """校验 JavaScript 返回的矩形。"""
        if not isinstance(raw, dict):
            return None
        try:
            rect = {key: float(raw[key]) for key in ("x", "y", "width", "height")}
        except (KeyError, TypeError, ValueError):
            return None
        return rect if rect["width"] >= 10 and rect["height"] >= 10 else None

    _DETECT_SCRIPT = """() => {
        const selectors = %s;
        const rectOf = el => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {x:r.left, y:r.top, width:r.width, height:r.height,
                right:r.right, bottom:r.bottom};
        };
        const visible = r => Boolean(r && r.width >= 10 && r.height >= 10 &&
            r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight);
        const isCf = src => /challenges\\.cloudflare\\.com|turnstile|cdn-cgi\\/challenge/i.test(String(src || ""));
        const roots = [document];
        for (let index = 0; index < roots.length; index++) {
            for (const el of roots[index].querySelectorAll("*")) {
                if (el.shadowRoot) roots.push(el.shadowRoot);
            }
        }
        const containers = [];
        for (const root of roots) for (const selector of selectors) {
            for (const el of root.querySelectorAll(selector)) if (!containers.includes(el)) containers.push(el);
        }
        const frames = [];
        for (const root of roots) for (const frame of root.querySelectorAll("iframe")) {
            const rect = rectOf(frame);
            frames.push({rect, cf:isCf(frame.src || frame.getAttribute("src"))});
        }
        let rect = null, target_kind = "none";
        const cf = frames.find(item => item.cf && visible(item.rect));
        if (cf) { rect = cf.rect; target_kind = "cf_iframe"; }
        if (!rect) {
            const sized = frames.find(item => visible(item.rect) && item.rect.width >= 100 && item.rect.height >= 40 && item.rect.height <= 120);
            if (sized) { rect = sized.rect; target_kind = "sized_iframe"; }
        }
        if (!rect) for (const container of containers) {
            const frame = container.querySelector && container.querySelector("iframe");
            const candidate = rectOf(frame) || rectOf(container);
            if (visible(candidate)) { rect = candidate; target_kind = frame ? "container_iframe" : "container"; break; }
        }
        const token = document.querySelector(%s);
        return {present:Boolean(containers.length || frames.some(item => item.cf) || window.turnstile || token),
            visible:visible(rect), rect, target_kind, source:"dom_container"};
    }""" % (
        repr(list(CONTAINER_SELECTORS)),
        repr(TOKEN_SELECTOR),
    )


class TurnstileHandler:
    """移动鼠标点击可见 Turnstile 并等待响应令牌。"""

    CHECKBOX_OFFSET_X = 28.0

    def __init__(
        self,
        page: Any,
        detector: TurnstileDetector | None = None,
    ) -> None:
        """创建 Turnstile 鼠标处理器。"""
        self.page = page
        self.detector = detector or TurnstileDetector(page)

    async def handle(
        self,
        timeout: float = 30.0,
        click_interval: float = 8.0,
        max_clicks: int = 3,
    ) -> bool:
        """只在显示验证时移动鼠标点击并等待 token。"""
        deadline = time.monotonic() + max(0.0, timeout)
        clicks = 0
        while time.monotonic() < deadline:
            if len(await self.detector.get_token()) > 10:
                return True
            snapshot = await self.detector.detect()
            if not snapshot.visible or snapshot.rect is None:
                return False
            if clicks >= max_clicks:
                return False
            await self._click_checkbox(snapshot.rect)
            clicks += 1
            token_deadline = min(deadline, time.monotonic() + max(0.0, click_interval))
            while time.monotonic() < token_deadline:
                if len(await self.detector.get_token()) > 10:
                    return True
                await self._sleep(0.3, token_deadline)
        return len(await self.detector.get_token()) > 10

    async def _click_checkbox(self, rect: dict[str, float]) -> None:
        """按容器左侧复选框位置执行全局移动点击。"""
        x = rect["x"] + min(self.CHECKBOX_OFFSET_X, max(1.0, rect["width"] - 1.0))
        y = rect["y"] + rect["height"] / 2.0
        x = max(0.0, x + random.uniform(-3.0, 3.0))
        y = max(0.0, y + random.uniform(-3.0, 3.0))

        async def click() -> None:
            """执行一次快速移动和按压点击。"""
            await self.page.mouse.move(x, y, steps=1)
            await self.page.mouse.down()
            await self.page.wait_for_timeout(30)
            await self.page.mouse.up()

        await asyncio.wait_for(click(), timeout=2.0)

    async def _sleep(self, seconds: float, deadline: float) -> None:
        """在总截止时间内等待, 避免重试阻塞超时。"""
        remaining = max(0.0, deadline - time.monotonic())
        if remaining:
            await asyncio.sleep(min(seconds, remaining))
