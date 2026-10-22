"""Provider 领域服务装配。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.database.unit_of_work import UnitOfWorkFactory
from app.services.providers.provider_catalog_service import ProviderCatalogService
from app.infrastructure.providers.code_loader import ProviderCodeLoader
from app.services.providers.provider_config_service import ProviderConfigService
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.services.providers.provider_payload_factory import ProviderPayloadFactory
from app.infrastructure.providers.provider_runtime import ProviderRuntime
from app.services.providers.provider_sync_service import ProviderSyncService


@dataclass(slots=True)
class ProviderServices:
    """Provider 领域服务集合。"""

    config: ProviderConfigService
    execution: ProviderExecutionService
    sync: ProviderSyncService
    catalog: ProviderCatalogService


def build_provider_services(uow_factory: UnitOfWorkFactory) -> ProviderServices:
    """构造 Provider 领域服务集合。"""
    code_loader = ProviderCodeLoader()
    runtime = ProviderRuntime(code_loader=code_loader)
    payload_factory = ProviderPayloadFactory(code_loader=code_loader)
    config = ProviderConfigService(runtime=runtime, uow_factory=uow_factory)
    execution = ProviderExecutionService(
        runtime=runtime,
        config_service=config,
    )
    sync = ProviderSyncService(code_loader=code_loader, uow_factory=uow_factory)
    catalog = ProviderCatalogService(
        payload_factory=payload_factory,
        uow_factory=uow_factory,
    )
    return ProviderServices(
        config=config,
        execution=execution,
        sync=sync,
        catalog=catalog,
    )
