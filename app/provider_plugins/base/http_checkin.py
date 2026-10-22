"""HTTP 签到 Provider 通用流程模板。"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from curl_cffi import requests

from app.provider_plugins.base.provider import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult


class BaseHttpCheckinProvider(BaseProvider):
    """HTTP 签到模板: 签到前状态 → 签到 → 签到后状态 → 汇总结果。

    子类实现状态查询、签到动作与状态解析即可.
    """

    async def execute(self, config: ProviderConfig) -> ProviderResult:
        """执行标准 HTTP 签到流程。"""
        username = self.checkin_username(config)
        site_url = self.checkin_site_url(config)
        label = self.checkin_label()
        self.log(f"[{username}] 开始处理, 站点 {site_url}")
        try:
            initial_info = await self.fetch_status(config)
            self.log(f"[{username}] 签到前: {initial_info}")

            checkin_raw = await self.do_checkin(config)
            status = self.parse_checkin_status(checkin_raw, config)
            self.log(f"[{username}] 签到状态: {status}")

            final_info = await self.fetch_status(config)
            self.log(f"[{username}] 签到后: {final_info}")
        except requests.RequestsError as exc:
            self.log(f"[{username}] 站点请求失败: {exc}")
            return ProviderResult.fail(
                message=f"{label}站点请求失败",
                data={"error": str(exc), "site_url": site_url},
            )
        except ValueError as exc:
            self.log(f"[{username}] 站点处理失败: {exc}")
            return ProviderResult.fail(
                message=f"{label}站点处理失败",
                data={"error": str(exc), "site_url": site_url},
            )

        self.log(f"[{username}] 处理完成, 状态 {status}")
        return ProviderResult.ok(
            message=f"{label}处理完成: {status}",
            data={
                "status": status,
                "initial_info": initial_info,
                "final_info": final_info,
                "site_url": site_url,
            },
        )

    def checkin_label(self) -> str:
        """结果文案前缀, 默认用 Provider 名称。"""
        return self.name

    @abstractmethod
    def checkin_username(self, config: ProviderConfig) -> str:
        """返回用于日志的账号标识。"""

    @abstractmethod
    def checkin_site_url(self, config: ProviderConfig) -> str:
        """返回站点根地址。"""

    @abstractmethod
    async def fetch_status(self, config: ProviderConfig) -> Any:
        """查询签到前/后状态 (积分、分享率等)。"""

    @abstractmethod
    async def do_checkin(self, config: ProviderConfig) -> str:
        """执行签到, 返回原始响应文本。"""

    @abstractmethod
    def parse_checkin_status(self, raw: str, config: ProviderConfig) -> str:
        """解析签到状态文案。"""
