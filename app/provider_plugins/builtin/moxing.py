"""Moxing 论坛自动签到 Provider。"""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator

from app.provider_plugins.base import DEFAULT_FORUM_USER_AGENT, ForumClient
from app.provider_plugins.base.http_checkin import BaseHttpCheckinProvider
from app.provider_plugins.contracts import ProviderConfig

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


class MoxingProvider(BaseHttpCheckinProvider):
    """Moxing 论坛签到和积分查询 Provider。"""

    name = "moxing"
    config_schema = MoxingConfig
    USER_AGENT = DEFAULT_FORUM_USER_AGENT
    """Moxing 请求使用的浏览器标识。"""

    def checkin_label(self) -> str:
        """结果文案前缀。"""
        return "Moxing "

    def checkin_username(self, config: ProviderConfig) -> str:
        """返回账号标识。"""
        assert isinstance(config, MoxingConfig)
        return config.username

    def checkin_site_url(self, config: ProviderConfig) -> str:
        """返回站点根地址。"""
        assert isinstance(config, MoxingConfig)
        return config.base_url

    async def fetch_status(self, config: ProviderConfig) -> str:
        """查询用户积分。"""
        assert isinstance(config, MoxingConfig)
        forum = self._forum_for(config)
        headers = forum.request_headers(config.cookie)
        return await forum.user_info(headers)

    async def do_checkin(self, config: ProviderConfig) -> str:
        """发现并执行 Moxing 签到请求。"""
        assert isinstance(config, MoxingConfig)
        forum = self._forum_for(config)
        headers = forum.request_headers(config.cookie)
        response = await self._http_request(forum.credit_url, headers=headers)
        html = response.text
        if any(text in html for text in MOXING_ALREADY_SIGNED_TEXTS):
            return html

        sign_href = forum.find_first_link_in_element(html, MOXING_SIGN_ELEMENT_ID)
        if not sign_href:
            self.log(f"[{config.username}] 签到入口不存在")
            return "签到链接不存在, 可能今日已签到"

        sign_url = forum.absolute_url(sign_href)
        response = await self._http_request(sign_url, headers=headers)
        return response.text

    def parse_checkin_status(self, raw: str, config: ProviderConfig) -> str:
        """解析 Moxing 签到状态。"""
        del config
        if any(text in raw for text in MOXING_SIGN_SUCCESS_TEXTS):
            return "签到成功"
        if any(text in raw for text in MOXING_ALREADY_SIGNED_TEXTS):
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
