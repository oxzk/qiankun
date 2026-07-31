"""Zero 签到 Provider。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import ClassVar

from pydantic import Field, ValidationInfo, field_validator

from app.provider_plugins.base import BaseBrowserProvider
from app.provider_plugins.base.browser import BrowserDriver
from app.provider_plugins.contracts import BrowserProviderConfig, ProviderResult
from app.shared.errors import AppError

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # pragma: no cover - 未安装浏览器依赖时回退。
    PlaywrightTimeoutError = TimeoutError


class ZeroConfig(BrowserProviderConfig):
    """Zero Provider 配置。"""

    email: str = Field(description="登录邮箱")
    password: str = Field(description="登录密码")

    @field_validator("email", "password", mode="before")
    @classmethod
    def require_non_empty(cls, value: object, info: ValidationInfo) -> str:
        """校验邮箱/密码非空。"""
        label = "邮箱" if info.field_name == "email" else "密码"
        if value is None or not str(value).strip():
            raise ValueError(f"{label}不能为空")
        return str(value).strip()


@dataclass(frozen=True)
class CheckInResult:
    """签到执行结果。"""

    before_points: str | None
    after_points: str | None
    status: str


@dataclass(frozen=True)
class CheckinPageSnapshot:
    """签到页 DOM 快照。"""

    balance: str | None
    has_spin_button: bool
    spin_disabled: bool


class ZeroProvider(BaseBrowserProvider):
    """Zero 签到 Provider。"""

    name = "zero"
    config_schema = ZeroConfig
    default_wait_load_state: ClassVar[str | None] = "load"

    CHECKIN_URL: ClassVar[str] = "https://api.saviour.cc.cd/daily-checkin"
    EMAIL_SELECTOR: ClassVar[str] = "input[type='email']"
    AGREE_CONTINUE_SELECTOR: ClassVar[str] = "button:has-text('同意并继续')"
    AGREEMENT_SELECTOR: ClassVar[str] = "#login-agreement-consent"
    PASSWORD_SELECTOR: ClassVar[str] = "input[type='password']"
    LOGIN_SUBMIT_SELECTOR: ClassVar[str] = "form button[type='submit']"
    SPIN_BUTTON_SELECTOR: ClassVar[str] = "button.spin-button"
    CHECKIN_HERO_SELECTOR: ClassVar[str] = "section.checkin-hero"
    LOGIN_URL_KEYWORD: ClassVar[str] = "login"
    PAGE_LANDING_KEYWORDS: ClassVar[tuple[str, ...]] = ("login",)
    BALANCE_LABELS: ClassVar[tuple[str, ...]] = ("Current Balance", "当前余额")

    CHECK_IN_SUCCESS: ClassVar[str] = "签到成功"
    CHECK_IN_ALREADY_DONE: ClassVar[str] = "今日已签到"
    CHECK_IN_NOT_FOUND: ClassVar[str] = "未找到签到按钮"
    CHECK_IN_UNCONFIRMED: ClassVar[str] = "签到结果未确认"

    LOGIN_MAX_ATTEMPTS: ClassVar[int] = 2
    PAGE_READY_TIMEOUT_MS: ClassVar[int] = 15_000
    LOGIN_SUCCESS_TIMEOUT_MS: ClassVar[int] = 20_000
    CHECK_IN_RESULT_TIMEOUT_MS: ClassVar[int] = 12_000
    INITIAL_SPIN_DISABLED_RECHECK_MS: ClassVar[int] = 2_000
    SELECTOR_TIMEOUT_MS: ClassVar[int] = 10_000

    async def execute_with_browser(
        self,
        browser: BrowserDriver,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """在已启动浏览器中执行登录与签到流程。"""
        config = (
            provider_config
            if isinstance(provider_config, ZeroConfig)
            else ZeroConfig.model_validate(provider_config)
        )
        try:
            if await self.check_login(browser):
                self.log(f"需要登录, 当前地址 {browser.current_url()}")
                if not await self._login(browser, config):
                    return await self.fail_with_screenshot(
                        browser,
                        message="登录失败, 未能进入签到页",
                        reason="login_failed",
                        data={"url": browser.current_url()},
                    )
                self.log(f"登录成功, 已到达签到页 {browser.current_url()}")
            else:
                self.log(f"会话有效, 已在签到页 {browser.current_url()}")

            await self.wait_for_selector(
                browser,
                self.CHECKIN_HERO_SELECTOR,
                timeout_ms=self.PAGE_READY_TIMEOUT_MS,
            )
            return await self._build_check_in_result(browser, await self._check_in(browser))
        except Exception as exc:
            self.log(f"执行异常: {type(exc).__name__}: {exc}")
            return await self.fail_with_screenshot(
                browser,
                message=f"执行异常: {type(exc).__name__}",
                reason="execute_failed",
                data={"url": browser.current_url(), "error": str(exc)},
            )

    async def check_login(self, browser: BrowserDriver) -> bool:
        """打开签到页并判断是否需要登录。"""
        await self.open_url_and_check(
            browser,
            self.CHECKIN_URL,
            self.PAGE_LANDING_KEYWORDS,
            timeout_ms=self.PAGE_READY_TIMEOUT_MS,
        )
        return self.LOGIN_URL_KEYWORD in browser.current_url().lower()

    async def _build_check_in_result(
        self,
        browser: BrowserDriver,
        result: CheckInResult,
    ) -> ProviderResult:
        """按签到状态构造 ProviderResult。"""
        before_points = result.before_points
        after_points = result.after_points or (
            before_points if result.status == self.CHECK_IN_SUCCESS else result.after_points
        )
        points_change = (
            f"{before_points} -> {after_points}"
            if before_points and after_points
            else "-"
        )
        balance = after_points or before_points or "-"
        self.log(
            f"签到结束: {result.status}, 余额 {before_points or '-'} -> {after_points or '-'}"
        )
        data: dict[str, object] = {
            "before_points": before_points,
            "after_points": after_points,
            "points_change": points_change,
            "check_in_status": result.status,
            "url": browser.current_url(),
        }
        if result.status == self.CHECK_IN_ALREADY_DONE:
            return ProviderResult.ok(message=f"今日已签到, 余额 {balance}", data=data)
        if result.status == self.CHECK_IN_SUCCESS:
            return ProviderResult.ok(message=f"签到成功, 余额 {points_change}", data=data)
        if result.status == self.CHECK_IN_NOT_FOUND:
            message, reason = "未找到签到按钮", "spin_button_missing"
        elif result.status == self.CHECK_IN_UNCONFIRMED:
            message, reason = "签到结果未确认", "checkin_unconfirmed"
        else:
            message, reason = f"未知签到状态: {result.status}", "checkin_unknown"
        return await self.fail_with_screenshot(
            browser,
            message=message,
            reason=reason,
            data=data,
        )

    def _is_checkin_url(self, url: str) -> bool:
        """判断 URL 是否为签到页 (匹配 ``CHECKIN_URL`` 路径)。"""
        target = self.CHECKIN_URL.rstrip("/").lower()
        current = url.split("?", 1)[0].rstrip("/").lower()
        return current == target or current.endswith("/daily-checkin")

    async def _wait_for_login_success(self, browser: BrowserDriver) -> bool:
        """等待登录后进入签到页 (``CHECKIN_URL``)。"""

        def _on_checkin(current: str) -> bool:
            return self._is_checkin_url(current)

        try:
            await browser.wait_for_url(_on_checkin, timeout=self.LOGIN_SUCCESS_TIMEOUT_MS)
            return True
        except PlaywrightTimeoutError:
            return self._is_checkin_url(browser.current_url())

    async def _login(self, browser: BrowserDriver, config: ZeroConfig) -> bool:
        """填写表单并登录, 成功返回 True, 仍停登录页返回 False。"""
        try:
            await self.wait_for_selector_click(
                browser,
                self.AGREE_CONTINUE_SELECTOR,
                timeout_ms=3_000,
            )
        except Exception:
            pass

        # 协议勾选可选: 页面无该节点时跳过.
        agreement = await self.wait_for_selector(
            browser,
            self.AGREEMENT_SELECTOR,
            timeout_ms=self.SELECTOR_TIMEOUT_MS,
        )
        if agreement is not None:
            await agreement.click(timeout=self.SELECTOR_TIMEOUT_MS)

        await self.wait_for_selector_fill(
            browser,
            self.EMAIL_SELECTOR,
            config.email,
            timeout_ms=self.SELECTOR_TIMEOUT_MS,
        )
        await self.wait_for_selector_fill(
            browser,
            self.PASSWORD_SELECTOR,
            config.password,
            timeout_ms=self.SELECTOR_TIMEOUT_MS,
        )
        self.log(f"登录表单已填写 ({config.email})")

        for attempt in range(1, self.LOGIN_MAX_ATTEMPTS + 1):
            self.log(f"开始登录 ({attempt}/{self.LOGIN_MAX_ATTEMPTS})")
            if await self.is_turnstile_visible(browser):
                self.log("存在人机验证, 开始处理")
                if not await self.handle_visible_turnstile(browser):
                    if attempt >= self.LOGIN_MAX_ATTEMPTS:
                        raise AppError("人机验证失败")
                    self.log("人机验证未通过, 准备重试")
                    continue

            await self.wait_for_selector_click(
                browser,
                self.LOGIN_SUBMIT_SELECTOR,
                timeout_ms=self.SELECTOR_TIMEOUT_MS,
            )
            self.log("已提交登录, 等待进入签到页")
            if await self._wait_for_login_success(browser):
                return True
            if attempt < self.LOGIN_MAX_ATTEMPTS and await self.is_turnstile_visible(browser):
                self.log("仍未进入签到页, 将再次处理人机验证后重试")
                continue
            break
        return False

    async def _check_in(self, browser: BrowserDriver) -> CheckInResult:
        """执行签到并返回结构化结果。"""
        snapshot = await self._ensure_checkin_snapshot(browser)
        before = snapshot.balance
        if snapshot.spin_disabled:
            self.log(f"签到按钮不可用, 视为已签到, 余额 {before or '-'}")
        elif snapshot.has_spin_button:
            self.log(f"可以签到, 当前余额 {before or '-'}")
        else:
            self.log(f"未找到签到按钮, 当前余额 {before or '-'}")

        if snapshot.spin_disabled:
            return CheckInResult(before, snapshot.balance or before, self.CHECK_IN_ALREADY_DONE)
        if not snapshot.has_spin_button:
            return CheckInResult(before, snapshot.balance or before, self.CHECK_IN_NOT_FOUND)

        await self.wait_for_selector_click(
            browser,
            self.SPIN_BUTTON_SELECTOR,
            timeout_ms=self.SELECTOR_TIMEOUT_MS,
        )
        self.log("已点击签到, 等待结果")
        after, status = await self._confirm_check_in_result(
            browser,
            before_points=before,
        )
        return CheckInResult(before, after, status)

    async def _ensure_checkin_snapshot(self, browser: BrowserDriver) -> CheckinPageSnapshot:
        """读取签到页快照, 排除按钮短暂禁用的加载状态。"""
        snapshot = await self._read_checkin_snapshot(browser)
        if snapshot.spin_disabled:
            await browser.wait_for_timeout(self.INITIAL_SPIN_DISABLED_RECHECK_MS)
            return await self._read_checkin_snapshot(browser)
        if snapshot.has_spin_button:
            return snapshot
        await self.wait_for_any_selector(
            browser,
            (self.SPIN_BUTTON_SELECTOR, self.CHECKIN_HERO_SELECTOR),
            timeout_ms=self.SELECTOR_TIMEOUT_MS,
        )
        return await self._read_checkin_snapshot(browser)

    async def _confirm_check_in_result(
        self,
        browser: BrowserDriver,
        *,
        before_points: str | None,
    ) -> tuple[str | None, str]:
        """轮询签到页快照确认签到结果。"""
        deadline = time.monotonic() + self.CHECK_IN_RESULT_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            snapshot = await self._read_checkin_snapshot(browser)
            current = snapshot.balance
            if before_points is not None and current is not None and current != before_points:
                self.log(f"签到完成 (余额变化 {before_points} -> {current})")
                return current, self.CHECK_IN_SUCCESS
            await browser.wait_for_timeout(self.ELEMENT_POLL_MS)

        snapshot = await self._read_checkin_snapshot(browser)
        if before_points is not None and snapshot.balance is not None and snapshot.balance != before_points:
            self.log(f"签到完成 (余额变化 {before_points} -> {snapshot.balance})")
            return snapshot.balance, self.CHECK_IN_SUCCESS
        self.log(
            f"签到未确认: 余额未变化 "
            f"({before_points or '-'} -> {snapshot.balance or '-'})"
        )
        return snapshot.balance or before_points, self.CHECK_IN_UNCONFIRMED

    async def _read_checkin_snapshot(self, browser: BrowserDriver) -> CheckinPageSnapshot:
        """一次 evaluate 读取余额与抽奖按钮状态。"""
        try:
            raw = await browser.evaluate(
                """({ heroSelector, spinSelector, balanceLabels }) => {
                    const norm = (v) => String(v || "").trim();
                    const lower = (v) => norm(v).toLowerCase();
                    const hero = document.querySelector(heroSelector);
                    const heroText = hero ? String(hero.innerText || "") : "";

                    let balance = "";
                    if (hero) {
                        const labels = (balanceLabels || []).map((x) => lower(x));
                        const label = Array.from(hero.querySelectorAll("p")).find((el) => {
                            const t = lower(el.textContent);
                            return labels.some((item) => item && t.includes(item));
                        });
                        if (label && label.nextElementSibling) {
                            balance = norm(label.nextElementSibling.textContent);
                        }
                        if (!balance) {
                            const match = heroText.match(/\\$[\\d,]+(?:\\.\\d+)?/);
                            if (match) balance = match[0];
                        }
                        if (!balance) {
                            const num = heroText.match(
                                /(?:余额|Balance)[^\\d]*([\\d,]+(?:\\.\\d+)?)/i
                            );
                            if (num) balance = num[1];
                        }
                    }

                    const spin = document.querySelector(spinSelector);
                    const hasSpin = Boolean(spin);
                    const spinDisabled = hasSpin && Boolean(
                        spin.disabled
                        || spin.getAttribute("disabled") !== null
                        || spin.classList.contains("disabled")
                        || spin.getAttribute("aria-disabled") === "true"
                    );
                    return {
                        balance,
                        has_spin_button: hasSpin,
                        spin_disabled: spinDisabled,
                    };
                }""",
                {
                    "heroSelector": self.CHECKIN_HERO_SELECTOR,
                    "spinSelector": self.SPIN_BUTTON_SELECTOR,
                    "balanceLabels": list(self.BALANCE_LABELS),
                },
            )
        except Exception as exc:
            self.log(f"读取签到页状态失败: {type(exc).__name__}: {exc}", log_type="system")
            return CheckinPageSnapshot(None, False, False)

        raw = raw or {}
        return CheckinPageSnapshot(
            balance=self._normalize_balance(raw.get("balance")),
            has_spin_button=bool(raw.get("has_spin_button")),
            spin_disabled=bool(raw.get("spin_disabled")),
        )

    @staticmethod
    def _normalize_balance(value: object) -> str | None:
        """规范化余额文本: 去掉 US/USD 字样, 保留 ``$`` 与数值。"""
        text = str(value or "").strip()
        if not text:
            return None
        # US$17.53 / USD $17.53 / USD17.53 -> 统一为 $ + 数值.
        text = re.sub(r"(?i)^\s*us\s*d?\s*\$?\s*", "", text).strip()
        if not text:
            return None
        if not text.startswith("$"):
            # 纯数字时补上 $, 已有 $ 则保留.
            if re.match(r"^[\d,]+(?:\.\d+)?$", text):
                text = f"${text}"
        return text
