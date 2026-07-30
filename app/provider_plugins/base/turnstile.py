"""Cloudflare Turnstile 容器检测与全局鼠标处理。

对齐 demo_camoufox_turnstile.py:
  - 不进入 iframe, 对 widget 左侧 checkbox 做全局坐标点击
  - 优先 DOM 容器几何; 失败时回退 Playwright frames / CDP
  - 容器内 iframe 尺寸不可用时回退到容器自身 rect
  - 点击后轮询 cf-turnstile-response; 超时重算坐标再点
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable

from app.provider_plugins.base.turnstile_detect_script import build_detect_script
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnstileSnapshot:
    """Turnstile 检测快照。

    Attributes:
        present: 页面是否存在 Turnstile 特征。
        visible: 是否存在位于当前视口的可见组件。
        rect: 组件在页面视口中的矩形 ``{x, y, width, height}``。
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
    """综合 DOM / Playwright frames / CDP 检测 Turnstile 视口矩形。"""

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

    @classmethod
    def build_detect_script(cls) -> str:
        """构造 DOM 检测脚本。"""
        return build_detect_script(cls.CONTAINER_SELECTORS, cls.TOKEN_SELECTOR)

    def __init__(
        self,
        page: Any,
        log_func: Callable[..., None] | None = None,
    ) -> None:
        """创建 Turnstile 检测器。"""
        self.page = page
        self.log = log_func or (lambda *args, **kwargs: None)

    async def detect(self) -> TurnstileSnapshot:
        """综合检测 Turnstile, 优先返回带可用 rect 的可见快照。"""
        snap = await self._detect_via_dom()
        if snap.visible and snap.rect is not None:
            return snap

        pw = await self._detect_via_playwright_frames()
        if pw is not None and pw.rect is not None:
            return TurnstileSnapshot(
                present=True,
                visible=True,
                rect=pw.rect,
                source="playwright_frames",
                target_kind=pw.target_kind,
                token=snap.token or pw.token,
            )

        cdp = await self._detect_via_cdp()
        if cdp is not None and cdp.rect is not None:
            return TurnstileSnapshot(
                present=True,
                visible=True,
                rect=cdp.rect,
                source="cdp",
                target_kind=cdp.target_kind,
                token=snap.token or cdp.token,
            )

        # DOM 已有容器 rect 但可见性判定失败时, 仍按容器几何可用处理.
        if snap.rect is not None:
            return TurnstileSnapshot(
                present=True,
                visible=True,
                rect=snap.rect,
                source="dom_container",
                target_kind=snap.target_kind if snap.target_kind != "none" else "container",
                token=snap.token,
            )

        if cdp is not None:
            return TurnstileSnapshot(
                present=True,
                visible=cdp.visible,
                rect=cdp.rect,
                source="cdp",
                target_kind=cdp.target_kind,
                token=snap.token or cdp.token,
            )

        return snap

    async def wait_for_rect(self, deadline: float, poll_seconds: float = 0.5) -> TurnstileSnapshot:
        """轮询直到拿到可用 rect 或到达截止时间。"""
        last = TurnstileSnapshot()
        poll = 0
        while time.monotonic() < deadline:
            poll += 1
            last = await self.detect()
            if last.rect is not None and last.rect["width"] >= 10 and last.rect["height"] >= 10:
                return last
            if poll == 1 or poll % 5 == 0:
                self.log(
                    "Turnstile 轮询: "
                    f"n={poll}, present={last.present}, visible={last.visible}, "
                    f"kind={last.target_kind}, source={last.source}"
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_seconds, remaining))
        return last

    async def is_visible(self) -> bool:
        """返回页面上是否显示 Turnstile。"""
        return (await self.detect()).visible

    async def get_token(self) -> str:
        """读取页面中的 Turnstile 响应令牌。"""
        try:
            value = await self.page.evaluate(
                """() => {
                    const pick = (root) => {
                        if (!root || !root.querySelector) return "";
                        const el = root.querySelector(
                            'input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]'
                        );
                        return (el && el.value) ? String(el.value) : "";
                    };
                    let token = pick(document);
                    if (token) return token;
                    for (const selector of [
                        ".cf-turnstile",
                        ".turnstile-wrapper",
                        ".turnstile-container",
                        "[class*='turnstile']",
                        "#_ts_box",
                    ]) {
                        token = pick(document.querySelector(selector));
                        if (token) return token;
                    }
                    for (const el of document.querySelectorAll('[name="cf-turnstile-response"]')) {
                        if (el.value) return String(el.value);
                    }
                    return "";
                }"""
            )
        except Exception:
            return ""
        text = str(value or "").strip()
        return text if len(text) > 10 else ""

    async def _detect_via_dom(self) -> TurnstileSnapshot:
        """页面 JS 检测容器 / shadow / iframe 几何。"""
        try:
            raw = await self.page.evaluate(type(self).build_detect_script()) or {}
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
            token=str(raw.get("token") or ""),
        )

    async def _detect_via_playwright_frames(self) -> TurnstileSnapshot | None:
        """通过 Playwright page.frames 获取 CF iframe bounding_box。"""
        try:
            for frame in self.page.frames:
                if not self._is_turnstile_frame_url(getattr(frame, "url", "") or ""):
                    continue
                try:
                    element = await frame.frame_element()
                    box = await element.bounding_box()
                except Exception:
                    continue
                rect = self._normalize_box(box)
                if rect is None:
                    continue
                return TurnstileSnapshot(
                    present=True,
                    visible=True,
                    rect=rect,
                    source="playwright_frames",
                    target_kind="pw_frame",
                )
        except Exception as exc:
            self.log(f"Turnstile Playwright frames 检测异常: {exc}")
        return None

    async def _detect_via_cdp(self) -> TurnstileSnapshot | None:
        """通过 CDP Page.getFrameTree 定位跨域 Turnstile iframe。"""
        client = None
        try:
            client = await self.page.context.new_cdp_session(self.page)
            tree = await client.send("Page.getFrameTree")
            frames = self._walk_cdp_frames(tree)
            if not frames:
                return None
            urls = {item["url"] for item in frames}
            for frame in self.page.frames:
                if getattr(frame, "url", "") not in urls:
                    continue
                try:
                    element = await frame.frame_element()
                    box = await element.bounding_box()
                except Exception:
                    continue
                rect = self._normalize_box(box)
                if rect is not None:
                    return TurnstileSnapshot(
                        present=True,
                        visible=True,
                        rect=rect,
                        source="cdp",
                        target_kind="cdp_frame",
                    )
            return TurnstileSnapshot(
                present=True,
                visible=False,
                rect=None,
                source="cdp",
                target_kind="cdp_url_only",
            )
        except Exception as exc:
            self.log(f"Turnstile CDP 检测异常: {exc}")
            return None
        finally:
            if client is not None:
                try:
                    await client.detach()
                except Exception:
                    pass

    @staticmethod
    def _is_turnstile_frame_url(url: object) -> bool:
        """判断 frame URL 是否属于 Cloudflare Turnstile。"""
        if not isinstance(url, str):
            return False
        text = url.lower()
        return (
            "challenges.cloudflare.com" in text
            or "turnstile" in text
            or "cdn-cgi/challenge" in text
        )

    @classmethod
    def _walk_cdp_frames(cls, tree: object) -> list[dict[str, str]]:
        """从 CDP frameTree 提取 Turnstile frame。"""
        if not isinstance(tree, dict):
            return []
        root = tree.get("frameTree")
        if not isinstance(root, dict):
            return []
        result: list[dict[str, str]] = []
        pending: list[object] = [root]
        while pending:
            node = pending.pop()
            if not isinstance(node, dict):
                continue
            frame = node.get("frame")
            if isinstance(frame, dict):
                frame_id, url = frame.get("id"), frame.get("url")
                if isinstance(frame_id, str) and cls._is_turnstile_frame_url(url):
                    result.append({"id": frame_id, "url": str(url)})
            children = node.get("childFrames")
            if isinstance(children, list):
                pending.extend(item for item in children if isinstance(item, dict))
        return result

    @classmethod
    def _normalize_rect(cls, raw: object) -> dict[str, float] | None:
        """校验并规范化 JavaScript 返回的矩形。"""
        if not isinstance(raw, dict):
            return None
        try:
            # 兼容 demo 的 w/h 与生产的 width/height.
            width = raw.get("width", raw.get("w"))
            height = raw.get("height", raw.get("h"))
            rect = {
                "x": float(raw["x"]),
                "y": float(raw["y"]),
                "width": float(width),
                "height": float(height),
            }
        except (KeyError, TypeError, ValueError):
            return None
        return rect if rect["width"] >= 10 and rect["height"] >= 10 else None

    @classmethod
    def _normalize_box(cls, box: dict[str, float] | None) -> dict[str, float] | None:
        """规范化 Playwright bounding_box。"""
        if not box:
            return None
        try:
            width = float(box.get("width") or 0)
            height = float(box.get("height") or 0)
            if width < 10 or height < 10:
                return None
            return {
                "x": float(box.get("x") or 0),
                "y": float(box.get("y") or 0),
                "width": width,
                "height": height,
            }
        except (TypeError, ValueError):
            return None


class TurnstileHandler:
    """移动鼠标点击可见 Turnstile 并等待响应令牌。"""

    CHECKBOX_OFFSET_X = 28.0

    def __init__(
        self,
        page: Any,
        detector: TurnstileDetector | None = None,
        log_func: Callable[..., None] | None = None,
    ) -> None:
        """创建 Turnstile 鼠标处理器。"""
        self.page = page
        self.detector = detector or TurnstileDetector(page, log_func=log_func)
        self.log = log_func or getattr(self.detector, "log", lambda *args, **kwargs: None)

    async def handle(
        self,
        timeout: float = 45.0,
        click_interval: float = 10.0,
        max_clicks: int = 5,
    ) -> bool:
        """等待可见 widget, 全局点击 checkbox 并轮询 token。

        Args:
            timeout: 总处理时限, 秒。
            click_interval: 无 token 时重新点击的间隔, 秒。
            max_clicks: 最大点击次数。
        """
        deadline = time.monotonic() + max(0.0, timeout)

        # 已自动通过则直接成功.
        if len(await self.detector.get_token()) > 10:
            self.log("Turnstile 点击前已有 token")
            return True

        snapshot = await self.detector.wait_for_rect(deadline)
        if snapshot.rect is None:
            self.log(
                "Turnstile 未找到可用矩形: "
                f"present={snapshot.present}, kind={snapshot.target_kind}, "
                f"source={snapshot.source}"
            )
            return False

        self.log(
            "Turnstile 已定位: "
            f"kind={snapshot.target_kind}, source={snapshot.source}, "
            f"rect=({snapshot.rect['x']:.0f},{snapshot.rect['y']:.0f},"
            f"{snapshot.rect['width']:.0f}x{snapshot.rect['height']:.0f})"
        )
        return await self._click_and_wait_token(
            rect=snapshot.rect,
            deadline=deadline,
            click_interval=click_interval,
            max_clicks=max_clicks,
        )

    async def _click_and_wait_token(
        self,
        *,
        rect: dict[str, float],
        deadline: float,
        click_interval: float,
        max_clicks: int,
    ) -> bool:
        """点击后轮询 token; 间隔到期无 token 则重算坐标再点。"""
        current_rect = rect
        clicks = 0
        last_click_at = 0.0

        while time.monotonic() < deadline:
            if len(await self.detector.get_token()) > 10:
                self.log(f"Turnstile 已拿到 token, 点击次数={clicks}")
                return True

            now = time.monotonic()
            need_click = clicks == 0 or (now - last_click_at) >= max(0.0, click_interval)
            if not need_click:
                await self._sleep(0.3, deadline)
                continue

            if clicks >= max_clicks:
                await self._sleep(0.3, deadline)
                continue

            # 重试时重新检测坐标, 失败则沿用上次 rect.
            if clicks > 0:
                refreshed = await self.detector.detect()
                if refreshed.rect is not None:
                    current_rect = refreshed.rect
                    self.log(
                        "Turnstile 重算坐标: "
                        f"kind={refreshed.target_kind}, source={refreshed.source}, "
                        f"rect=({current_rect['x']:.0f},{current_rect['y']:.0f},"
                        f"{current_rect['width']:.0f}x{current_rect['height']:.0f})"
                    )

            clicked = await self._click_checkbox(current_rect)
            clicks += 1
            last_click_at = time.monotonic()
            if not clicked:
                # 点击本身失败时立刻允许再点, 不空等整段间隔.
                last_click_at = time.monotonic() - max(0.0, click_interval)
                self.log(f"Turnstile 第 {clicks} 次点击失败, 将立即重试")

        ok = len(await self.detector.get_token()) > 10
        if not ok:
            self.log(f"Turnstile 超时未拿到 token, 点击次数={clicks}")
        return ok

    async def _click_checkbox(self, rect: dict[str, float]) -> bool:
        """按容器左侧复选框位置执行全局移动点击。"""
        width = float(rect.get("width") or rect.get("w") or 0)
        height = float(rect.get("height") or rect.get("h") or 0)
        x = float(rect["x"]) + min(self.CHECKBOX_OFFSET_X, max(1.0, width - 1.0))
        y = float(rect["y"]) + height / 2.0
        x = max(0.0, x + random.uniform(-3.0, 3.0))
        y = max(0.0, y + random.uniform(-3.0, 3.0))
        self.log(f"Turnstile 鼠标点击: x={x:.1f}, y={y:.1f}")

        async def click() -> None:
            """执行一次快速移动和按压点击。"""
            # steps=1 避免 camoufox humanize 把 move 拖到数十秒.
            await self.page.mouse.move(x, y, steps=1)
            await self.page.mouse.down()
            await self.page.wait_for_timeout(30)
            await self.page.mouse.up()

        try:
            await asyncio.wait_for(click(), timeout=2.0)
            # 点击后稍等, 给 widget 处理与 token 回写时间.
            await self.page.wait_for_timeout(2000)
            return True
        except Exception as exc:
            self.log(f"Turnstile 点击异常: {type(exc).__name__}: {exc}")
            return False

    async def _sleep(self, seconds: float, deadline: float) -> None:
        """在总截止时间内等待, 避免重试阻塞超时。"""
        remaining = max(0.0, deadline - time.monotonic())
        if remaining:
            await asyncio.sleep(min(seconds, remaining))
