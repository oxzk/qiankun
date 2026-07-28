"""Discuz Provider 通用能力。"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from html import unescape
from urllib.parse import urljoin

from bs4 import BeautifulSoup

DISCUZ_CREDIT_PATH = "/home.php?mod=spacecp&ac=credit&op=base"
"""Discuz 用户积分页路径。"""

DISCUZ_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)
"""Discuz 请求使用的浏览器标识。"""

RequestHtml = Callable[[str, dict[str, str]], Awaitable[str]]
"""Discuz HTML 请求函数类型。"""


CREDIT_CLEANUP_PATTERN = re.compile(r"&#13;|<em>|</em>|\(前往兌換商城\)|<[^>]+>|\r?\n")
"""积分文本清理规则。"""


class DiscuzForum:
    """封装 Discuz 论坛通用请求和页面解析。"""

    def __init__(
        self,
        base_url: str,
        username: str,
        request_html: RequestHtml,
    ) -> None:
        """初始化 Discuz 论坛封装。"""
        self.base_url = base_url.rstrip("/")
        self.username = username
        self._request_html = request_html

    @property
    def credit_url(self) -> str:
        """返回 Discuz 用户积分页地址。"""
        return f"{self.base_url}{DISCUZ_CREDIT_PATH}"

    def request_headers(self, cookie: str) -> dict[str, str]:
        """构造 Discuz 请求头。"""
        return {
            "Cookie": cookie,
            "Referer": self.credit_url,
            "User-Agent": DISCUZ_USER_AGENT,
        }

    async def user_info(self, headers: dict[str, str]) -> str:
        """查询并解析 Discuz 用户积分。"""
        html = await self.request_authenticated_html(self.credit_url, headers)
        return self.parse_credit_text(html)

    async def request_authenticated_html(
        self,
        url: str,
        headers: dict[str, str],
    ) -> str:
        """请求 Discuz 页面并验证 Cookie 登录状态。"""
        html = await self._request_html(url, headers)
        if self.username not in html:
            raise ValueError("登录状态已失效, 页面中未找到配置账号")
        return html

    def absolute_url(self, href: str) -> str:
        """返回基于站点根地址补全后的 URL。"""
        return urljoin(f"{self.base_url}/", href.lstrip("/"))

    @staticmethod
    def parse_credit_text(html: str) -> str:
        """从 Discuz 积分页 HTML 解析积分文本。"""
        soup = BeautifulSoup(html, "html.parser")
        credit_element = soup.select_one(".creditl")
        if credit_element is None:
            return ""
        content = CREDIT_CLEANUP_PATTERN.sub("", credit_element.get_text())
        content = unescape(content).strip()
        return "".join(content.split())

    @staticmethod
    def find_first_link_in_element(html: str, element_id: str) -> str | None:
        """查找指定元素内的首个链接。"""
        soup = BeautifulSoup(html, "html.parser")
        link_element = soup.select_one(f"#{element_id} a")
        if link_element is None:
            return None
        href = link_element.get("href")
        return href if isinstance(href, str) else None
