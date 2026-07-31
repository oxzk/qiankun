"""Provider 请求载荷工厂。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.database.models.provider import Provider
from app.infrastructure.providers.code_loader import ProviderCodeLoader
from app.provider_plugins.base import BaseProvider
from app.schemas.provider import ProviderCreate, ProviderUpdate


@dataclass(slots=True)
class ProviderPayloadValues:
    """Provider 创建和更新请求的归一化值。"""

    name: str


class ProviderPayloadFactory:
    """Provider 创建和更新请求归一化工厂。"""

    def __init__(self, code_loader: ProviderCodeLoader) -> None:
        """初始化 Provider 请求载荷工厂。"""
        self._code_loader = code_loader

    def resolve_payload_provider_class(
        self,
        payload: ProviderCreate | ProviderUpdate,
        *,
        actor: str | None = None,
        source: str = "api",
    ) -> type[BaseProvider]:
        """解析请求中的 Provider 类。"""
        return self._code_loader.load_provider_class_from_code(
            payload.name,
            payload.code,
            actor=actor,
            source=source,
        )

    def values_from_payload(
        self,
        payload: ProviderCreate | ProviderUpdate,
        *,
        actor: str | None = None,
        source: str = "api",
    ) -> ProviderPayloadValues:
        """从创建或更新请求构造归一化 Provider 值。"""
        self.resolve_payload_provider_class(payload, actor=actor, source=source)
        return ProviderPayloadValues(
            name=payload.name.strip(),
        )

    def from_create(
        self,
        payload: ProviderCreate,
        *,
        actor: str | None = None,
    ) -> Provider:
        """从创建请求构造 Provider 模型。"""
        values = self.values_from_payload(payload, actor=actor, source="create")
        return Provider(
            name=values.name,
            code=payload.code,
            enabled=payload.enabled,
        )

    def apply_update(
        self,
        provider: Provider,
        payload: ProviderUpdate,
        *,
        actor: str | None = None,
    ) -> ProviderPayloadValues:
        """将更新请求字段赋值到 Provider 模型并返回归一化值。"""
        values = self.values_from_payload(payload, actor=actor, source="update")
        provider.name = values.name
        provider.code = payload.code
        provider.enabled = payload.enabled
        return values
