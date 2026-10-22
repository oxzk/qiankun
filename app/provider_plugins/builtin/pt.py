"""PT 站点自动签到 Provider。"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator

from app.provider_plugins.base.http_checkin import BaseHttpCheckinProvider
from app.provider_plugins.contracts import ProviderConfig


class _InfoBlockExtractor(HTMLParser):
    """提取 PT 页面中的 info_block HTML 片段。"""

    VOID_ELEMENTS = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )
    """无需结束标签的 HTML 元素。"""

    def __init__(self) -> None:
        """初始化提取状态。"""
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self._found = False
        self._fragments: list[str] = []

    @property
    def html(self) -> str | None:
        """返回提取出的 info_block HTML。"""
        if not self._found:
            return None
        return "".join(self._fragments)

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """处理 HTML 开始标签并维护目标节点深度。"""
        if self._depth == 0:
            if self._found or dict(attrs).get("id") != "info_block":
                return
            self._found = True
            self._depth = 1
            self._fragments.append(self.get_starttag_text())
            return

        self._fragments.append(self.get_starttag_text())
        if tag not in self.VOID_ELEMENTS:
            self._depth += 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """处理 HTML 自闭合标签。"""
        if self._depth > 0:
            self._fragments.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        """处理 HTML 结束标签并结束完整目标节点提取。"""
        if self._depth == 0:
            return
        self._fragments.append(f"</{tag}>")
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        """保留目标节点中的文本数据。"""
        if self._depth > 0:
            self._fragments.append(escape(data, quote=False))


class PtConfig(ProviderConfig):
    """PT Provider 配置。"""

    base_url: str = Field(description="PT 站点根地址")
    cookie: str = Field(description="PT 站点登录 Cookie")
    username: str = Field(description="PT 站点账号")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """校验并规范化 PT 站点根地址。"""
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PT 站点根地址必须是有效的 HTTP 或 HTTPS URL")
        return normalized

    @field_validator("cookie", "username")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """校验并规范化必填文本配置。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return normalized


class PtProvider(BaseHttpCheckinProvider):
    """PT 站点自动签到和用户信息查询 Provider。"""

    name = "pt"
    config_schema = PtConfig

    CREDIT_PATTERN = (
        r"<font\s*class=['\"]color_(ratio|uploaded|downloaded)['\"]>([^<]+)</font>\s*"
    )
    """上传量, 下载量和分享率字段匹配规则。"""

    BONUS_PATTERN = (
        r'<font.*?>([^<]+)</font>\[<a href="mybonus.php">使用</a>\]:\s*([\d,.]+)'
    )
    """魔力值字段匹配规则。"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
    """PT 请求使用的浏览器标识。"""

    def checkin_label(self) -> str:
        """结果文案前缀。"""
        return "PT "

    def checkin_username(self, config: ProviderConfig) -> str:
        """返回账号标识。"""
        assert isinstance(config, PtConfig)
        return config.username

    def checkin_site_url(self, config: ProviderConfig) -> str:
        """返回站点根地址。"""
        assert isinstance(config, PtConfig)
        return config.base_url

    async def fetch_status(self, config: ProviderConfig) -> str | None:
        """查询并解析 PT 账号信息。"""
        assert isinstance(config, PtConfig)
        headers = self._request_headers(config)
        response = await self._http_request(
            f"{config.base_url}/mybonus.php",
            headers=headers,
        )
        if config.username not in response.text:
            raise ValueError("登录状态已失效, 页面中未找到配置账号")
        return self._parse_user_info(response.text)

    async def do_checkin(self, config: ProviderConfig) -> str:
        """按站点规则执行签到并返回响应正文。"""
        assert isinstance(config, PtConfig)
        headers = self._request_headers(config)
        base_url_lower = config.base_url.lower()
        if "qingwa" in base_url_lower:
            await self._http_request(
                f"{config.base_url}/shoutbox.php",
                method="POST",
                headers=headers,
                data={
                    "type": "shoutbox",
                    "sent": "yes",
                    "shout": "我喊",
                    "shbox_text": "蛙总，求上传",
                },
            )
            await self._http_request(
                f"{config.base_url}/api/bonus-shop/exchange",
                method="POST",
                headers=headers,
                data={"id": 28, "amount": 1},
            )

        checkin_url = f"{config.base_url}/attendance.php"
        if "btschool" in base_url_lower:
            checkin_url = f"{config.base_url}/index.php?action=addbonus"
        response = await self._http_request(checkin_url, headers=headers)
        return response.text

    def parse_checkin_status(self, raw: str, config: ProviderConfig) -> str:
        """解析签到状态和连续签到奖励。"""
        assert isinstance(config, PtConfig)
        username = config.username
        if not raw:
            self.log(f"[{username}] 签到响应为空")
            return "签到响应为空"

        if "签到成功" in raw:
            bonus_match = re.search(
                r"已连续签到 <b>(\d+)</b> 天, 本次签到获得 <b>(\d+)</b>",
                raw.replace("，", ","),
                re.DOTALL,
            )
            if bonus_match is not None:
                bonus = re.sub(r"<[^>]+>", "", bonus_match.group())
                self.log(f"[{username}] 签到成功: {bonus}")
                return f"签到成功 - {bonus}"
            self.log(f"[{username}] 签到成功")
            return "签到成功"

        if "已经签到" in raw:
            self.log(f"[{username}] 今日已经签到")
            return "今日已经签到"
        return "签到已完成"

    def _parse_user_info(self, html: str) -> str | None:
        """从 info_block 中提取上传量, 下载量, 分享率和魔力值。"""
        parser = _InfoBlockExtractor()
        parser.feed(html)
        info_html = parser.html
        if info_html is None:
            return None

        user_data: dict[str, str] = {}
        credit_matches = re.findall(rf"{self.CREDIT_PATTERN}([\d.,]+)", info_html)
        for _, name, value in credit_matches:
            clean_name = re.sub(r"[:|：]", "", name).strip()
            user_data[clean_name] = value.strip()

        bonus_matches = re.findall(self.BONUS_PATTERN, info_html)
        for name, value in bonus_matches:
            user_data[name.strip()] = value.strip().replace(",", "")

        if not user_data:
            return "无法解析用户信息"
        return "; ".join(f"{key}: {value}" for key, value in user_data.items())

    @staticmethod
    def _request_headers(config: PtConfig) -> dict[str, str]:
        """构造 PT 请求头。"""
        return {
            "Cookie": config.cookie,
            "Referer": f"{config.base_url}/mybonus.php",
            "User-Agent": PtProvider.USER_AGENT,
        }
