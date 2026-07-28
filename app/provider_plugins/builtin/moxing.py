"""Moxing 论坛自动签到 Provider。"""

from __future__ import annotations

from urllib.parse import urlsplit

from curl_cffi import requests
from pydantic import Field, ValidationInfo, field_validator

from app.provider_plugins.base import BaseProvider, DEFAULT_FORUM_USER_AGENT, ForumClient
from app.provider_plugins.contracts import ProviderConfig, ProviderResult

MOXING_SIGN_SUCCESS_TEXTS = ("签到成功", "已签到", "今天已签")
"""Moxing 签到成功或已签到文本。"""

MOXING_ALREADY_SIGNED_TEXTS = ("今日已签", "已经签到", "重复签到")
"""Moxing 已签到文本。"""

MOXING_SIGN_ELEMENT_ID = "k_misign_topb"
"""Moxing 签到入口元素 ID。"""


class MoxingConfig(ProviderConfig):
    """Moxing Provider 配置。"""

    base_url: str = Field(description="Moxing 站点根地址")
    cookie: str = Field(description="Moxing 登录 Cookie")
    username: str = Field(description="Moxing 账号")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """校验并规范化 Moxing 站点根地址。"""
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Moxing 站点根地址必须是有效的 HTTP 或 HTTPS URL")
        return normalized

    @field_validator("cookie", "username")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """校验并规范化必填文本配置。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return normalized


class MoxingProvider(BaseProvider):
    """Moxing 论坛签到和积分查询 Provider。"""

    name = "moxing"
    config_schema = MoxingConfig
    USER_AGENT = DEFAULT_FORUM_USER_AGENT
    """Moxing 请求使用的浏览器标识。"""

    async def execute(
        self,
        config: ProviderConfig,
    ) -> ProviderResult:
        """执行 Moxing 签到前查询, 签到和签到后查询流程。"""
        typed_config = MoxingConfig.model_validate(config)
        forum = self._forum_for(typed_config)
        headers = forum.request_headers(typed_config.cookie)
        self.log(f"[{typed_config.username}] Moxing 处理开始, 站点 {typed_config.base_url}")
        try:
            initial_info = await forum.user_info(headers)
            self.log(f"[{typed_config.username}] Moxing 签到前积分: {initial_info}")

            checkin_result = await self._checkin(typed_config, forum, headers)
            status = self._parse_checkin_status(checkin_result)
            self.log(f"[{typed_config.username}] Moxing 签到状态: {status}")

            final_info = await forum.user_info(headers)
            self.log(f"[{typed_config.username}] Moxing 签到后积分: {final_info}")
        except requests.RequestsError as exc:
            self.log(f"[{typed_config.username}] Moxing 站点请求失败: {exc}")
            return ProviderResult.fail(
                message="Moxing 站点请求失败",
                data={"error": str(exc), "site_url": typed_config.base_url},
            )
        except ValueError as exc:
            self.log(f"[{typed_config.username}] Moxing 站点处理失败: {exc}")
            return ProviderResult.fail(
                message="Moxing 站点处理失败",
                data={"error": str(exc), "site_url": typed_config.base_url},
            )

        self.log(f"[{typed_config.username}] Moxing 处理完成, 状态 {status}")
        return ProviderResult.ok(
            message=f"Moxing 处理完成: {status}",
            data={
                "status": status,
                "initial_info": initial_info,
                "final_info": final_info,
                "site_url": typed_config.base_url,
            },
        )

    async def _checkin(
        self,
        config: MoxingConfig,
        forum: ForumClient,
        headers: dict[str, str],
    ) -> str:
        """发现并执行 Moxing 签到请求。"""
        response = await self._http_request(forum.credit_url, headers=headers)
        html = response.text
        if any(text in html for text in MOXING_ALREADY_SIGNED_TEXTS):
            return html

        sign_href = forum.find_first_link_in_element(html, MOXING_SIGN_ELEMENT_ID)
        if not sign_href:
            self.log(f"[{config.username}] Moxing 签到入口不存在")
            return "签到链接不存在, 可能今日已签到"

        sign_url = forum.absolute_url(sign_href)
        response = await self._http_request(sign_url, headers=headers)
        return response.text

    def _parse_checkin_status(self, html: str) -> str:
        """解析 Moxing 签到状态。"""
        if any(text in html for text in MOXING_SIGN_SUCCESS_TEXTS):
            return "签到成功"
        if any(text in html for text in MOXING_ALREADY_SIGNED_TEXTS):
            return "今日已签到"
        return "签到完成"

    def _forum_for(self, config: MoxingConfig) -> ForumClient:
        """构造当前 Moxing 账号的论坛封装。"""
        return ForumClient(
            base_url=config.base_url,
            username=config.username,
            request_html=self._request_html,
        )

    async def _request_html(self, url: str, headers: dict[str, str]) -> str:
        """请求页面并返回 HTML 文本。"""
        response = await self._http_request(url, headers=headers)
        return response.text
