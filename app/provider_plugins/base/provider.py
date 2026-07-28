"""Provider 基础能力。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from curl_cffi import requests

from app.infrastructure.http.requester import Requester
from app.provider_plugins.contracts import (
    ProviderConfig,
    ProviderContext,
    ProviderResult,
    format_provider_log,
)
from app.shared.logger import logger


class BaseProvider(ABC):
    """内置 Provider 基类。"""

    name: ClassVar[str]
    config_schema: ClassVar[type[ProviderConfig]] = ProviderConfig

    def __init__(self, requester: Requester | None = None) -> None:
        """初始化 Provider 基础 HTTP 请求类型占位。"""
        self._requester: Requester | None = requester
        self._owns_requester = requester is None
        self._logs: list[str] = []

    @property
    def requester(self) -> Requester:
        """获取或创建 Provider HTTP 请求器。"""
        requester = getattr(self, "_requester", None)
        if requester is None:
            requester = Requester()
            self._requester = requester
            self._owns_requester = True
        return requester

    async def run(self, config: ProviderConfig, context: ProviderContext) -> ProviderResult:
        """执行 Provider 并统一异常返回。"""
        self._logs = []
        try:
            try:
                result = await self.execute(config)
            except Exception as exc:
                logger.exception("Provider %s 执行失败: %s", self.name, exc)
                self.log(f"Provider {self.name} 执行失败: {type(exc).__name__}")
                result = ProviderResult.fail(
                    message=f"Provider {self.name} 执行失败: {type(exc).__name__}",
                    data={"error": str(exc)},
                )
            result.logs = list(self._logs)
            return result
        finally:
            await self._close_owned_requester()

    def log(self, content: str) -> str:
        """记录并返回 Provider 执行日志。"""
        formatted_log = format_provider_log(content)
        self._logs.append(formatted_log)
        logger.info("Provider %s: %s", self.name, content)
        return formatted_log

    async def _http_request(
        self,
        url: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> requests.Response:
        """使用 Provider 共享 Requester 发送 HTTP 请求。"""
        if (kwargs.get("data") or kwargs.get("json")) and method.upper() == "GET":
            method = "POST"
        return await self.requester.request(method, url, **kwargs)

    async def _close_owned_requester(self) -> None:
        """关闭当前 Provider 自行创建的 Requester。"""
        requester = getattr(self, "_requester", None)
        if getattr(self, "_owns_requester", False) and requester is not None:
            await requester.close()
            self._requester = None

    @abstractmethod
    async def execute(
        self,
        config: ProviderConfig,
    ) -> ProviderResult:
        """执行 Provider 业务逻辑。"""
