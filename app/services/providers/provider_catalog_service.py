"""Provider 服务模块。"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory, commit_on_success
from app.schemas.provider import ProviderCreate, ProviderUpdate
from app.services.common.lookup import get_required
from app.services.common.pagination import PageQuery, PagedResult
from app.services.providers.provider_payload_factory import ProviderPayloadFactory
from app.shared.errors import AppError
from app.shared.logger import logger


class ProviderCatalogService:
    """Provider 目录管理服务。"""

    def __init__(
        self,
        payload_factory: ProviderPayloadFactory,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化 Provider 管理服务。"""
        self._payload_factory = payload_factory
        self._uow_factory = uow_factory

    async def list_providers(
        self,
        pagination: PageQuery,
        enabled: bool | None = None,
    ) -> PagedResult[Provider]:
        """分页列出 Provider。"""
        async with self._uow_factory() as uow:
            items, total = await uow.providers.list_paginated(
                pagination.page,
                pagination.page_size,
                enabled,
            )
        return PagedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def get_provider(self, provider_name: str) -> Provider:
        """获取 Provider 详情。"""
        async with self._uow_factory() as uow:
            provider = await get_required(
                uow.providers.get_by_name,
                provider_name,
                "Provider 不存在",
            )
        return provider

    async def create_provider(
        self,
        payload: ProviderCreate,
        *,
        actor: str | None = None,
    ) -> Provider:
        """创建 Provider。"""
        provider = self._payload_factory.from_create(payload, actor=actor)

        async def create_unique(uow: UnitOfWork) -> Provider:
            """创建不重名的 Provider。"""
            if await uow.providers.get_by_name(provider.name) is not None:
                raise AppError("Provider 已存在")
            try:
                created = await uow.providers.create(provider)
            except IntegrityError as exc:
                raise AppError("Provider 已存在", status_code=409) from exc
            logger.info(
                "Provider 已创建: name=%s actor=%s code_bytes=%s",
                created.name,
                actor or "-",
                len(payload.code.encode("utf-8")),
            )
            return created

        return await commit_on_success(self._uow_factory, create_unique)

    async def update_provider(
        self,
        provider_name: str,
        payload: ProviderUpdate,
        *,
        actor: str | None = None,
    ) -> Provider:
        """更新 Provider。"""

        async def update_existing(uow: UnitOfWork) -> Provider:
            """更新已存在 Provider。"""
            provider = await get_required(
                uow.providers.get_by_name,
                provider_name,
                "Provider 不存在",
            )
            values = self._payload_factory.apply_update(provider, payload, actor=actor)
            duplicate = await uow.providers.get_by_name(values.name)
            if duplicate is not None and duplicate.id != provider.id:
                raise AppError("Provider 已存在")

            try:
                updated = await uow.providers.update(provider)
            except IntegrityError as exc:
                raise AppError("Provider 已存在", status_code=409) from exc
            logger.info(
                "Provider 已更新: name=%s actor=%s code_bytes=%s",
                updated.name,
                actor or "-",
                len(payload.code.encode("utf-8")),
            )
            return updated

        return await commit_on_success(self._uow_factory, update_existing)

    async def set_enabled(self, provider_name: str, enabled: bool) -> Provider:
        """启用或禁用 Provider。"""

        async def update_enabled(uow: UnitOfWork) -> Provider:
            """更新 Provider 启用状态。"""
            provider = await get_required(
                uow.providers.get_by_name,
                provider_name,
                "Provider 不存在",
            )
            provider.enabled = enabled
            return await uow.providers.update(provider)

        return await commit_on_success(self._uow_factory, update_enabled)
