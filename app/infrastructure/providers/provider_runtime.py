"""Provider 运行时服务。"""

from __future__ import annotations

from pydantic import ValidationError

from app.infrastructure.database.models.provider import Provider
from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import (
    ProviderContext,
    ProviderResult,
    ProviderValidateResult,
    format_provider_log,
)
from app.infrastructure.providers.code_loader import ProviderCodeLoader


class ProviderRuntime:
    """Provider 类加载, 配置校验和运行服务。"""

    def __init__(self, code_loader: ProviderCodeLoader) -> None:
        """初始化 Provider 执行服务。"""
        self._code_loader = code_loader

    def resolve_model_provider_class(self, provider: Provider) -> type[BaseProvider]:
        """解析数据库模型中的 Provider 类。"""
        return self._code_loader.load_provider_class_from_code(provider.name, provider.code)

    async def validate_config(
        self,
        provider: Provider,
        config: dict[str, object],
    ) -> ProviderValidateResult:
        """校验 Provider 配置。"""
        provider_class = self.resolve_model_provider_class(provider)
        try:
            typed_config = provider_class.config_schema.model_validate(config)
        except ValidationError as exc:
            return ProviderValidateResult(valid=False, error=str(exc))
        return ProviderValidateResult(valid=True, config=typed_config.model_dump(mode="json"))

    async def run_provider(
        self,
        provider: Provider,
        config: dict[str, object],
        context: ProviderContext,
    ) -> ProviderResult:
        """执行指定 Provider 模型。"""
        provider_class = self.resolve_model_provider_class(provider)
        return await self.run_provider_class(provider_class, config, context)

    async def run_provider_class(
        self,
        provider_class: type[BaseProvider],
        config: dict[str, object],
        context: ProviderContext,
    ) -> ProviderResult:
        """校验配置并执行 Provider 类。"""
        try:
            typed_config = provider_class.config_schema.model_validate(config)
        except ValidationError as exc:
            message = f"Provider 配置无效: {exc}"
            return ProviderResult(
                success=False,
                message=message,
                logs=[format_provider_log(message)],
            )
        provider = provider_class()
        return await provider.run(typed_config, context)
