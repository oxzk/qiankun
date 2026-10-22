"""Provider 基础能力。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

from curl_cffi import requests
from pydantic import ValidationError

from app.infrastructure.http.requester import Requester
from app.provider_plugins.contracts import (
    ProviderConfig,
    ProviderContext,
    ProviderResult,
    format_provider_log,
)
from app.shared.errors import AppError
from app.shared.logger import logger

ProviderLogType = Literal["provider", "system"]
"""Provider 日志类型: provider 业务日志 / system 系统日志。"""


class BaseProvider(ABC):
    """内置 Provider 基类。"""

    name: ClassVar[str]
    config_schema: ClassVar[type[ProviderConfig]] = ProviderConfig

    def __init__(self, requester: Requester | None = None) -> None:
        """初始化 Provider 基础 HTTP 请求类型占位。"""
        self._requester: Requester | None = requester
        self._owns_requester = requester is None
        self._logs: list[str] = []
        self._context: ProviderContext | None = None

    @property
    def requester(self) -> Requester:
        """获取或创建 Provider HTTP 请求器。"""
        requester = getattr(self, "_requester", None)
        if requester is None:
            requester = Requester()
            self._requester = requester
            self._owns_requester = True
        return requester

    @property
    def context(self) -> ProviderContext:
        """当前执行上下文 (由 ``run`` 注入)。"""
        if self._context is None:
            raise AppError("ProviderContext 未初始化, 请通过 run() 执行")
        return self._context

    async def run(
        self,
        config: ProviderConfig | dict[str, Any],
        context: ProviderContext,
    ) -> ProviderResult:
        """校验配置、注入上下文并执行 Provider。

        配置只在此处校验一次; 子类 ``execute`` 收到的已是 ``config_schema`` 实例.
        """
        self._logs = []
        self._context = context
        try:
            try:
                typed_config = self._coerce_config(config)
                result = await self.execute(typed_config)
            except ValidationError as exc:
                message = self._format_config_error(exc)
                self.log(message)
                result = ProviderResult.fail(
                    message=message,
                    data={"error": type(exc).__name__},
                )
            except Exception as exc:
                logger.exception("Provider %s 执行失败: %s", self.name, exc)
                self.log(f"执行失败: {type(exc).__name__}")
                result = ProviderResult.fail(
                    message=f"Provider {self.name} 执行失败: {type(exc).__name__}",
                    data={"error": str(exc)},
                )
            result.logs = list(self._logs)
            return result
        finally:
            self._context = None
            await self._close_owned_requester()

    def _coerce_config(self, config: ProviderConfig | dict[str, Any]) -> ProviderConfig:
        """将输入配置规范为 ``config_schema`` 实例 (已是实例则直接返回)。"""
        if isinstance(config, self.config_schema):
            return config
        return self.config_schema.model_validate(config)

    def _format_config_error(self, exc: ValidationError) -> str:
        """格式化配置校验错误。"""
        first_error = exc.errors()[0] if exc.errors() else {}
        message = str(first_error.get("msg") or exc)
        return f"{self.name} 配置错误: {message}"

    def log(self, content: str, *, log_type: ProviderLogType = "provider") -> None:
        """记录日志并用 ``logger`` 输出。

        Args:
            content: 日志正文, 必须是 ``str``.
            log_type: ``provider`` 写入 ``result.logs`` (经 ``format_provider_log``);
                ``system`` 仅输出到 logger, 不做 Provider 格式转换, 不进入 result.logs.
        """
        if not isinstance(content, str):
            raise TypeError(
                f"log content 必须是 str, 实际为 {type(content).__name__}"
            )
        if log_type not in ("provider", "system"):
            raise ValueError(f"log_type 仅支持 provider|system, 实际为 {log_type!r}")

        logger.info("Provider %s: %s", self.name, content)
        if log_type == "system":
            return
        self._logs.append(format_provider_log(content))

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
    async def execute(self, config: ProviderConfig) -> ProviderResult:
        """执行 Provider 业务逻辑 (``config`` 已通过 ``config_schema`` 校验)。"""
