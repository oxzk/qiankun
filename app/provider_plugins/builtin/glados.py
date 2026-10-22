"""GLaDOS 自动签到和剩余天数查询 Provider."""

from __future__ import annotations

import math
import re
from typing import Any, ClassVar
from urllib.parse import urlsplit

from curl_cffi import requests
from pydantic import Field

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult


class GladosAccount(ProviderConfig):
    """GLaDOS 单账号配置, 登录凭据与设备标识必须来自同一次登录."""

    base_url: str = Field(default="https://glados.one", description="GLaDOS 登录站点根地址")
    username: str = Field(description="GLaDOS 登录邮箱或账号标识")
    cookie: str = Field(description="GLaDOS 完整登录 Cookie")
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
        ),
        description="获取 Cookie 时浏览器使用的 User-Agent",
    )
    token: str | None = Field(default=None, description="签到 token, 未设置时使用站点域名")


class GladosConfig(ProviderConfig):
    """GLaDOS 多账号签到配置."""

    accounts: list[GladosAccount] = Field(min_length=1, description="GLaDOS 账号列表")


class GladosProvider(BaseProvider):
    """使用固定登录设备执行 GLaDOS 签到并查询账号剩余天数."""

    name = "glados"
    """Provider 注册名称."""
    config_schema = GladosConfig
    """GLaDOS 配置校验模型."""
    REPEAT_MESSAGE: ClassVar[str] = "Checkin Repeats! Please Try Tomorrow"
    """上游明确表示今日已经签到的响应消息."""

    async def execute(self, config: ProviderConfig) -> ProviderResult:
        """逐个处理账号并汇总结果, 任一账号失败时将整体标记为失败."""
        assert isinstance(config, GladosConfig)
        results: list[ProviderResult] = []
        for account in config.accounts:
            results.append(await self._check_account(account))

        data = {
            "targets": [
                {**result.data, "success": result.success, "message": result.message}
                for result in results
            ]
        }
        if all(result.success for result in results):
            return ProviderResult.ok(message="GLaDOS 全部账号处理完成", data=data)
        return ProviderResult.fail(message="GLaDOS 存在失败账号", data=data)

    async def _check_account(self, config: GladosAccount) -> ProviderResult:
        """执行单账号签到和状态查询, 保留签到结果以区分后续状态查询失败."""
        data: dict[str, Any] = {"site_url": config.base_url, "username": config.username}
        stage = "签到"
        try:
            self.log(f"[{config.username}] 开始 GLaDOS 签到, 站点 {config.base_url}")
            payload = await self._request_api(
                config,
                "/user/checkin",
                method="POST",
                json={"token": config.token or urlsplit(config.base_url).hostname},
            )
            data.update(self._parse_checkin(payload))
            self.log(f"[{config.username}] {data['status']}")

            stage = "状态查询"
            payload = await self._request_api(config, "/user/status")
            self._assert_success_code(payload)
            account = payload.get("data")
            left_days = self._number(account.get("leftDays")) if isinstance(account, dict) else None
            if left_days is None:
                raise ValueError("状态响应缺少有效的 leftDays")
            data["left_days"] = left_days
            self.log(f"[{config.username}] 剩余 {left_days:g} 天")
        except (requests.RequestsError, ValueError) as exc:
            message = f"GLaDOS {stage}失败: {exc}"
            self.log(f"[{config.username}] {message}")
            return ProviderResult.fail(message=message, data={**data, "error": str(exc)})

        return ProviderResult.ok(
            message=f"GLaDOS {data['status']}, 剩余 {data['left_days']:g} 天",
            data=data,
        )

    async def _request_api(
        self,
        config: GladosAccount,
        endpoint: str,
        *,
        method: str = "GET",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """请求 GLaDOS API, 校验 HTTP 状态, 响应格式和授权."""
        response = await self._http_request(
            f"{config.base_url}/api{endpoint}",
            method=method,
            headers=self._request_headers(config),
            timeout=30,
            follow_redirects=False,
            raise_for_status=False,
            **kwargs,
        )
        if response.status_code in {401, 403}:
            raise ValueError(f"HTTP {response.status_code}, {self._login_hint(config)}")
        response.raise_for_status()
        if not 200 <= response.status_code < 300:
            raise ValueError(f"API 返回非成功状态 HTTP {response.status_code}")

        # 部分上游网关将故障正文包装成 HTTP 200, 保留网关错误以便定位原因.
        gateway = re.match(r"error code:\s*(502|503|504)\b", response.text.strip(), re.IGNORECASE)
        if gateway:
            raise ValueError(f"{endpoint} 上游临时故障: {gateway.group(1)}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError(f"{endpoint} 响应不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{endpoint} 响应必须是 JSON 对象")

        message = str(payload.get("message") or "")
        code = str(payload.get("code"))
        if code == "-2" or "没有权限" in message or "unauthorized" in message.lower():
            raise ValueError(self._login_hint(config))
        if payload.get("reason") == "device-mismatch":
            raise ValueError(f"登录设备不一致 (device-mismatch), {self._login_hint(config)}")
        if code == "4" or "automated check-in detected" in message.lower():
            raise ValueError(
                f"服务端拒绝自动签到, {self._login_hint(config)}; "
                "仍被拒绝时请使用官网手动签到"
            )
        return payload

    def _parse_checkin(self, payload: dict[str, Any]) -> dict[str, Any]:
        """解析新旧签到消息, 仅接受成功或明确的重复签到响应."""
        message = str(payload.get("message") or "").strip()
        code = str(payload.get("code"))
        if message == self.REPEAT_MESSAGE and code in {"0", "1"}:
            status = "今日已签到"
            points = None
        else:
            self._assert_success_code(payload)
            points = self._number(payload.get("points"))
            match = re.search(r"Checkin! Got\s+(\d+(?:\.\d+)?)\s+Points?", message, re.IGNORECASE)
            if message == "Please Try Tomorrow":
                raise ValueError("签到未完成, 请明天再试")
            if match:
                points = float(match.group(1))
                status = f"签到成功, 获得 {points:g} 积分"
            elif "Today's observation logged" in message:
                status = "签到成功, 今日观察已记录"
            elif points is not None:
                status = f"签到成功, 获得 {points:g} 积分"
            else:
                raise ValueError(f"无法识别签到结果: {message or '缺少 message'}")

        data: dict[str, Any] = {"status": status, "message": message}
        if points is not None:
            data["points"] = points
        history = payload.get("list")
        if isinstance(history, list) and history and isinstance(history[0], dict):
            balance = self._number(history[0].get("balance"))
            if balance is not None:
                data["balance"] = balance
        return data

    @staticmethod
    def _assert_success_code(payload: dict[str, Any]) -> None:
        """拒绝缺失或非零业务状态码, 避免将错误响应中的积分误认为签到成功."""
        if str(payload.get("code")) != "0":
            raise ValueError(
                f"API 业务失败 (code={payload.get('code')}): "
                f"{payload.get('message') or '缺少成功状态码'}"
            )

    @staticmethod
    def _number(value: Any) -> float | None:
        """解析有限数值, 拒绝布尔值及无效积分或天数."""
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return None
        try:
            number = float(value)
        except (ValueError, OverflowError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _login_hint(config: GladosAccount) -> str:
        """生成更新同一次登录凭据和设备标识的操作提示."""
        return f"请在 {config.base_url}/login 重新登录, 更新同一次登录的完整 Cookie 和 user_agent"

    @staticmethod
    def _request_headers(config: GladosAccount) -> dict[str, str]:
        """为签到, 查询和重试使用相同的登录设备与会话请求头."""
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": config.cookie,
            "Origin": config.base_url,
            "Referer": f"{config.base_url}/console/checkin",
            "User-Agent": config.user_agent,
        }
