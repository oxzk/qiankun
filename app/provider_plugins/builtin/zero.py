"""Zero 签到 Provider。"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field, field_validator

from app.provider_plugins.base import BaseBrowserProvider, BaseCamoufox
from app.provider_plugins.contracts import BrowserProviderConfig, ProviderResult
from app.shared.logger import logger
try:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # pragma: no cover - 未安装浏览器依赖时回退。
    PlaywrightTimeoutError = TimeoutError


class ZeroConfig(BrowserProviderConfig):
    """Zero Provider 配置。"""

    email: str | None = Field(default="atfangwenxue@gmail.com", description="登录邮箱")
    password: str | None = Field(default="B*bw@eI3n@i4^w", description="登录密码")

    @field_validator("email", "password", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        """规范化可选登录文本配置。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ZeroProvider(BaseBrowserProvider):
    """Zero 签到 Provider。

    打开签到页, 若跳转到登录页则使用邮箱密码登录并处理 Turnstile,
    再读取积分并点击抽奖按钮完成签到。
    """

    name = "zero"
    config_schema = ZeroConfig
    CHECKIN_URL: ClassVar[str] = "https://api.saviour.cc.cd/daily-checkin"
    EMAIL_SELECTOR: ClassVar[str] = "input[type='email']"
    AGREEMENT_SELECTOR: ClassVar[str] = "#login-agreement-consent"
    PASSWORD_SELECTOR: ClassVar[str] = "input[type='password']"
    LOGIN_SUBMIT_SELECTOR: ClassVar[str] = "form button[type='submit']"
    SPIN_BUTTON_SELECTOR: ClassVar[str] = "button.spin-button"
    POINTS_SELECTOR: ClassVar[str] = ".count-up-value"
    LOGIN_URL_KEYWORD: ClassVar[str] = "login"
    CHECK_IN_UNCONFIRMED: ClassVar[str] = "签到结果未确认"
    LOGIN_MAX_ATTEMPTS: ClassVar[int] = 2
    PAGE_READY_TIMEOUT_MS: ClassVar[int] = 15_000
    LOGIN_SUCCESS_TIMEOUT_MS: ClassVar[int] = 20_000
    CHECK_IN_RESULT_TIMEOUT_MS: ClassVar[int] = 12_000

    async def execute_with_browser(
        self,
        browser: BaseCamoufox,
        provider_config: BrowserProviderConfig,
    ) -> ProviderResult:
        """在已启动浏览器中执行登录与签到流程。"""
        config = ZeroConfig.model_validate(provider_config)
        try:
            # URL 含 login 表示被重定向到登录页, 需要登录.
            needs_login = await self.open_url_and_check(
                browser,
                self.CHECKIN_URL,
                self.LOGIN_URL_KEYWORD,
                timeout_ms=self.PAGE_READY_TIMEOUT_MS,
            )

            if needs_login:
                self.log(f"检测到登录页: {browser.current_url()}")
                if not await self._login(browser, config):
                    return await self.fail_with_screenshot(
                        browser,
                        message="Zero 登录失败, 当前仍为登录页",
                        reason="login_failed",
                        data={"url": browser.current_url()},
                    )
                self.log(f"登录成功: {browser.current_url()}")
                # 登录成功后重新进入签到页, 确保后续读取积分与点击按钮.
                still_on_login = await self.open_url_and_check(
                    browser,
                    self.CHECKIN_URL,
                    self.LOGIN_URL_KEYWORD,
                    timeout_ms=self.PAGE_READY_TIMEOUT_MS,
                )
                if still_on_login:
                    return await self.fail_with_screenshot(
                        browser,
                        message="Zero 登录后无法进入签到页",
                        reason="post_login_checkin_failed",
                        data={"url": browser.current_url()},
                    )
            else:
                self.log(f"已登录, 当前页面: {browser.current_url()}")

            before_points = await self._get_points(browser, navigate=False)
            self.log(f"签到前积分: {before_points or '-'}")

            check_in_status = await self._check_in(browser, before_points=before_points)

            after_points = await self._get_points(browser, navigate=True)
            # 若点击后已通过积分变化确认成功, 优先保留签到后读到的最新积分.
            if after_points is None and check_in_status == self.CHECK_IN_SUCCESS:
                after_points = before_points
            self.log(f"签到后积分: {after_points or '-'}")

            points_change = (
                f"{before_points} -> {after_points}"
                if before_points and after_points
                else "-"
            )
            self.log(f"签到状态: {check_in_status}")
            self.log(f"积分变化: {points_change}")

            data: dict[str, object] = {
                "before_points": before_points,
                "after_points": after_points,
                "points_change": points_change,
                "check_in_status": check_in_status,
                "url": browser.current_url(),
            }
            if check_in_status == self.CHECK_IN_NOT_FOUND:
                return await self.fail_with_screenshot(
                    browser,
                    message="Zero 未找到签到按钮",
                    reason="spin_button_missing",
                    data=data,
                )
            if check_in_status == self.CHECK_IN_UNCONFIRMED:
                return await self.fail_with_screenshot(
                    browser,
                    message="Zero 签到结果未确认",
                    reason="checkin_unconfirmed",
                    data=data,
                )
            if check_in_status == self.CHECK_IN_ALREADY_DONE:
                return ProviderResult.ok(
                    message=f"Zero 今日已签到 ({after_points or before_points or '-'})",
                    data=data,
                )
            return ProviderResult.ok(
                message=f"Zero 签到成功 ({points_change})",
                data=data,
            )
        except Exception as exc:
            logger.exception("Zero 执行失败: %s", exc)
            self.log(f"Zero 执行失败: {type(exc).__name__}: {str(exc)}")
            return await self.fail_with_screenshot(
                browser,
                message=f"Zero 执行失败: {type(exc).__name__}",
                reason="execute_failed",
                data={"url": browser.current_url(), "error": str(exc)},
            )

    def _is_login_url(self, browser: BaseCamoufox) -> bool:
        """判断当前 URL 是否包含 login。"""
        return self.LOGIN_URL_KEYWORD in browser.current_url().lower()

    async def _wait_for_login_success(
        self,
        browser: BaseCamoufox,
        timeout_ms: int | None = None,
    ) -> bool:
        """通过 ``wait_for_url`` 等待 URL 离开 login, 判定登录成功。

        超时视为未成功 (返回 False), 供登录重试使用; 其他异常向上抛出.
        """
        timeout = timeout_ms or self.LOGIN_SUCCESS_TIMEOUT_MS
        keyword = self.LOGIN_URL_KEYWORD.lower()

        def _left_login(current: str) -> bool:
            # URL 不再包含 login 关键字即视为已离开登录页.
            return keyword not in current.lower()

        try:
            await browser.wait_for_url(_left_login, timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return not self._is_login_url(browser)

    async def _login(
        self,
        browser: BaseCamoufox,
        config: ZeroConfig,
    ) -> bool:
        """使用邮箱密码登录: 先检测并处理 Turnstile, 再提交, 有限次重试。

        Returns:
            登录成功返回 True, 仍停留在登录页返回 False.
        """
        await browser.page.wait_for_load_state("networkidle")
        await browser.page.wait_for_timeout(2000)
        await browser.locator(self.AGREEMENT_SELECTOR).click(timeout=10000)
        await browser.page.wait_for_timeout(2000)

        await browser.locator(self.EMAIL_SELECTOR).fill(config.email)
        await browser.page.wait_for_timeout(500)
        await browser.locator(self.PASSWORD_SELECTOR).fill(config.password)
        self.log(f"已填写登录表单: {config.email}")
        await browser.page.wait_for_timeout(1000)

        if await self.is_turnstile_visible(browser):
            self.log("检测到 Turnstile, 先完成验证再提交")
            await self.handle_visible_turnstile(browser)

        await browser.page.wait_for_timeout(10000)

        # submit = browser.locator(self.LOGIN_SUBMIT_SELECTOR).first
        # await submit.wait_for(state="visible", timeout=10000)

        # for attempt in range(1, self.LOGIN_MAX_ATTEMPTS + 1):
        #     self.log(f"登录尝试 {attempt}/{self.LOGIN_MAX_ATTEMPTS}")

        #     # 先检测 Turnstile: 可见则完成验证, 再提交登录表单.
        #     if await self.is_turnstile_visible(browser):
        #         self.log("检测到 Turnstile, 先完成验证再提交")
        #         await self.handle_visible_turnstile(browser)
        #     else:
        #         self.log("未检测到 Turnstile, 直接提交")

        #     await submit.click(timeout=10000)
        #     self.log("已提交登录表单, 等待登录结果")

        #     if await self._wait_for_login_success(browser):
        #         return True

        #     # 仍停在登录态: 若还有可见 Turnstile 则进入下一轮, 否则失败。
        #     if attempt >= self.LOGIN_MAX_ATTEMPTS:
        #         break
        #     if not await self.is_turnstile_visible(browser):
        #         self.log("登录未成功且无可见 Turnstile, 停止重试")
        #         break
        #     self.log("登录未成功, 准备再次处理 Turnstile 后重试")

        return False

    async def _check_in(
        self,
        browser: BaseCamoufox,
        *,
        before_points: str | None,
    ) -> str:
        """点击抽奖按钮, 并通过按钮状态或积分变化确认结果。"""
        found = await self.wait_for_any_selector(
            browser,
            (self.SPIN_BUTTON_SELECTOR,),
            timeout_ms=10_000,
        )
        if not found:
            self.log("未找到抽奖按钮")
            return self.CHECK_IN_NOT_FOUND

        button = browser.locator(self.SPIN_BUTTON_SELECTOR).first
        if await button.is_disabled():
            return self.CHECK_IN_ALREADY_DONE

        await button.click(timeout=10000)
        self.log("已点击抽奖按钮, 等待结果确认")
        return await self._confirm_check_in_result(
            browser,
            button=button,
            before_points=before_points,
        )

    async def _confirm_check_in_result(
        self,
        browser: BaseCamoufox,
        *,
        button: object,
        before_points: str | None,
    ) -> str:
        """通过按钮 disabled 或积分变化确认签到结果。"""
        deadline = time.monotonic() + self.CHECK_IN_RESULT_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            if await button.is_disabled():  # type: ignore[attr-defined]
                self.log("签到按钮已禁用, 判定签到完成")
                return self.CHECK_IN_SUCCESS

            current_points = await self._read_points_text(browser)
            if (
                before_points is not None
                and current_points is not None
                and current_points != before_points
            ):
                self.log(f"积分已变化: {before_points} -> {current_points}")
                return self.CHECK_IN_SUCCESS

            await browser.wait_for_timeout(self.ELEMENT_POLL_MS)

        # 超时后做最终判定: 按钮禁用视为成功; 积分不变且仍可点视为未确认。
        if await button.is_disabled():  # type: ignore[attr-defined]
            return self.CHECK_IN_SUCCESS

        current_points = await self._read_points_text(browser)
        if (
            before_points is not None
            and current_points is not None
            and current_points != before_points
        ):
            return self.CHECK_IN_SUCCESS

        self.log("签到后按钮仍可点且积分未变化, 结果未确认")
        return self.CHECK_IN_UNCONFIRMED

    async def _get_points(
        self,
        browser: BaseCamoufox,
        *,
        navigate: bool = True,
    ) -> str | None:
        """读取当前积分数值。"""
        if navigate:
            await browser.goto(self.CHECKIN_URL)
            ready = await self.wait_for_any_selector(
                browser,
                (self.POINTS_SELECTOR, self.SPIN_BUTTON_SELECTOR),
                timeout_ms=self.PAGE_READY_TIMEOUT_MS,
            )
            if not ready:
                self.log("刷新签到页后未找到积分节点")
                return None
        return await self._read_points_text(browser)

    async def _read_points_text(self, browser: BaseCamoufox) -> str | None:
        """读取积分节点文本, 节点不存在时返回 None。"""
        if not await self.is_selector_visible(browser, self.POINTS_SELECTOR):
            return None
        value = await browser.locator(self.POINTS_SELECTOR).first.inner_text(timeout=3000)
        text = value.strip() if value else ""
        return text or None
