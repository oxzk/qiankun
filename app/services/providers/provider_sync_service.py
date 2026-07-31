"""Provider 同步服务。"""

from __future__ import annotations

from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.infrastructure.providers.builtin_provider_registry import BuiltinProviderRegistry, builtin_provider_registry
from app.infrastructure.database.models.provider import Provider
from app.infrastructure.providers.code_loader import ProviderCodeLoader


class ProviderSyncService:
    """内置 Provider 同步服务。"""

    def __init__(
        self,
        code_loader: ProviderCodeLoader,
        manager: BuiltinProviderRegistry | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化 Provider 同步服务。"""
        self._manager = manager or builtin_provider_registry
        self._code_loader = code_loader
        self._uow_factory = uow_factory

    async def sync_builtin_providers(self) -> None:
        """将代码中可发现的内置 Provider 同步到数据库。"""
        self._manager.load_providers()
        async with self._uow_factory() as uow:
            for item in self._manager.list_infos():
                provider_name = str(item["name"])
                provider_code = self._code_loader.source_code_for_provider_class(
                    item["provider_class"]
                )
                # 同步前校验源码可加载。
                self._code_loader.validate_provider_code(provider_name, provider_code)
                existing = await uow.providers.get_by_name(provider_name)
                if existing is None:
                    await uow.providers.create(
                        Provider(
                            name=provider_name,
                            code=provider_code,
                            enabled=True,
                        )
                    )
                    continue

                existing.code = provider_code
                await uow.providers.update(existing)
            await uow.commit()
