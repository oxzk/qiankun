"""Provider 执行应用服务。"""

from __future__ import annotations

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderContext, ProviderResult
from app.shared.enums import TriggerType
from app.services.providers.provider_config_service import ProviderConfigService
from app.infrastructure.providers.provider_runtime import ProviderRuntime


class ProviderExecutionService:
    """Provider 执行应用服务。"""

    def __init__(
        self,
        runtime: ProviderRuntime,
        config_service: ProviderConfigService,
    ) -> None:
        """初始化 Provider 执行应用服务。"""
        self._runtime = runtime
        self._config_service = config_service

    async def run_provider(
        self,
        provider_name: str,
        config: dict[str, object],
        context: ProviderContext,
    ) -> ProviderResult:
        """执行指定 Provider。"""
        provider = await self._config_service.get_enabled_provider_model(provider_name)
        return await self._runtime.run_provider(provider, config, context)

    async def test_run_provider(
        self,
        provider_name: str,
        config: dict[str, object],
    ) -> ProviderResult:
        """测试运行指定 Provider。"""
        provider = await self._config_service.get_enabled_provider_model(provider_name)
        provider_class = self._runtime.resolve_model_provider_class(provider)
        return await self.test_run_provider_class(provider_class, provider.name, config)

    async def test_run_provider_class(
        self,
        provider_class: type[BaseProvider],
        provider_name: str,
        config: dict[str, object],
    ) -> ProviderResult:
        """测试运行指定 Provider 类。"""
        return await self._runtime.run_provider_class(
            provider_class,
            config,
            ProviderContext(
                task_id=0,
                task_name=f"Provider 测试: {provider_name}",
                execution_id=None,
                trigger_type=TriggerType.MANUAL,
            ),
        )
