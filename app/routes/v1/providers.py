"""Provider API 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import (
    CurrentUserDep,
    get_provider_config_service,
    get_provider_execution_service,
    get_provider_service,
    get_provider_sync_service,
)
from app.schemas.provider import (
    ProviderCreate,
    ProviderInfo,
    ProviderTestRunRequest,
    ProviderUpdate,
    ProviderValidateRequest,
)
from app.provider_plugins.contracts import ProviderResult, ProviderValidateResult
from app.routes.dependencies import page_query
from app.routes.response_builders import build_page_response_from_result
from app.schemas.responses import APIResponse, PageResponse
from app.services.common.pagination import PageQuery
from app.services.providers.provider_catalog_service import ProviderCatalogService
from app.services.providers.provider_config_service import ProviderConfigService
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.services.providers.provider_sync_service import ProviderSyncService

router = APIRouter(prefix="/providers", tags=["providers"])
"""Provider 路由。"""


@router.get("", response_model=APIResponse[PageResponse[ProviderInfo]])
async def list_providers(
    pagination: PageQuery = Depends(page_query),
    enabled: bool | None = None,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[PageResponse[ProviderInfo]]:
    """分页查询 Provider。"""
    return build_page_response_from_result(
        await service.list_providers(pagination, enabled),
    )


@router.post("", response_model=APIResponse[ProviderInfo])
async def create_provider(
    payload: ProviderCreate,
    current_user: CurrentUserDep,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[ProviderInfo]:
    """创建 Provider。"""
    return await service.create_provider(payload, actor=current_user)


@router.post("/sync", response_model=APIResponse[bool])
async def sync_builtin_providers(
    service: ProviderSyncService = Depends(get_provider_sync_service),
) -> APIResponse[bool]:
    """同步内置 Provider。"""
    await service.sync_builtin_providers()
    return True


@router.get("/{provider_name}/config", response_model=APIResponse[dict[str, Any]])
async def get_provider_config(
    provider_name: str,
    service: ProviderConfigService = Depends(get_provider_config_service),
) -> APIResponse[dict[str, Any]]:
    """获取 Provider 配置。"""
    return await service.get_config(provider_name)


@router.get("/{provider_name}", response_model=APIResponse[ProviderInfo])
async def get_provider(
    provider_name: str,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[ProviderInfo]:
    """获取 Provider 详情。"""
    return await service.get_provider(provider_name)


@router.put("/{provider_name}", response_model=APIResponse[ProviderInfo])
async def update_provider(
    provider_name: str,
    payload: ProviderUpdate,
    current_user: CurrentUserDep,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[ProviderInfo]:
    """更新 Provider。"""
    return await service.update_provider(provider_name, payload, actor=current_user)


@router.post("/{provider_name}/enable", response_model=APIResponse[ProviderInfo])
async def enable_provider(
    provider_name: str,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[ProviderInfo]:
    """启用 Provider。"""
    return await service.set_enabled(provider_name, True)


@router.post("/{provider_name}/disable", response_model=APIResponse[ProviderInfo])
async def disable_provider(
    provider_name: str,
    service: ProviderCatalogService = Depends(get_provider_service),
) -> APIResponse[ProviderInfo]:
    """禁用 Provider。"""
    return await service.set_enabled(provider_name, False)


@router.post(
    "/{provider_name}/validate-config",
    response_model=APIResponse[ProviderValidateResult],
)
async def validate_provider_config(
    provider_name: str,
    payload: ProviderValidateRequest,
    service: ProviderConfigService = Depends(get_provider_config_service),
) -> APIResponse[ProviderValidateResult]:
    """校验 Provider 配置。"""
    return await service.validate_config(provider_name, payload.config)


@router.post(
    "/{provider_name}/test-run",
    response_model=APIResponse[ProviderResult],
)
async def test_run_provider(
    provider_name: str,
    payload: ProviderTestRunRequest,
    service: ProviderExecutionService = Depends(get_provider_execution_service),
) -> APIResponse[ProviderResult]:
    """测试运行 Provider。"""
    return await service.test_run_provider(provider_name, payload.config)
