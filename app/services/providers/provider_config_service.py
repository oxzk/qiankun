"""Provider 配置校验服务。"""

from __future__ import annotations

from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from app.shared.errors import AppError
from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.infrastructure.providers.provider_runtime import ProviderRuntime
from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderValidateResult
from app.services.common.lookup import get_required


class ProviderConfigService:
    """Provider 配置校验服务。"""

    def __init__(
        self,
        runtime: ProviderRuntime,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化 Provider 配置校验服务。"""
        self._runtime = runtime
        self._uow_factory = uow_factory

    async def validate_config(
        self,
        provider_name: str,
        config: dict[str, object],
    ) -> ProviderValidateResult:
        """校验 Provider 配置。"""
        provider = await self.get_enabled_provider_model(provider_name)
        return await self._runtime.validate_config(provider, config)

    async def get_config(self, provider_name: str) -> dict[str, object]:
        """获取 Provider 配置对象。"""
        provider = await self.get_provider_model(provider_name)
        provider_class = self._runtime.resolve_model_provider_class(provider)
        return self._config_from_provider_class(provider_class)

    async def get_enabled_provider_model(self, provider_name: str) -> Provider:
        """查询已启用 Provider 模型。"""
        provider = await self.get_provider_model(provider_name)
        if not provider.enabled:
            raise AppError("Provider 已禁用", status_code=400)
        return provider

    async def get_provider_model(self, provider_name: str) -> Provider:
        """查询 Provider 模型。"""
        async with self._uow_factory() as uow:
            return await get_required(
                uow.providers.get_by_name,
                provider_name,
                "Provider 不存在",
            )

    def _config_from_provider_class(
        self,
        provider_class: type[BaseProvider],
    ) -> dict[str, object]:
        """从 Provider 配置模型构造配置对象。"""
        return self._config_from_model(provider_class.config_schema)

    def _config_from_model(
        self,
        config_model: type[ProviderConfig],
        parent_models: frozenset[type[ProviderConfig]] = frozenset(),
    ) -> dict[str, object]:
        """递归构造 Provider 配置模型对应的配置对象。"""
        if config_model in parent_models:
            return {}

        config_schema = config_model.model_json_schema()
        properties = config_schema.get("properties")
        if not isinstance(properties, dict):
            return {}

        current_models = parent_models | {config_model}
        config: dict[str, object] = {}
        for key, schema_property in properties.items():
            if not isinstance(schema_property, dict):
                continue
            model_field = config_model.model_fields.get(key)
            nested_model, is_list = self._nested_config_model(
                model_field.annotation if model_field is not None else None,
            )
            config[key] = self._config_value(
                schema_property,
                nested_model,
                is_list,
                current_models,
            )
        return config

    def _config_value(
        self,
        schema_property: dict[str, Any],
        nested_model: type[ProviderConfig] | None = None,
        is_list: bool = False,
        parent_models: frozenset[type[ProviderConfig]] = frozenset(),
    ) -> object:
        """根据单个 JSON Schema 属性生成配置值。"""
        if "default" in schema_property and schema_property["default"] is not None:
            return schema_property["default"]

        if nested_model is not None:
            nested_config = self._config_from_model(nested_model, parent_models)
            return [nested_config] if is_list else nested_config

        enum_values = schema_property.get("enum")
        if isinstance(enum_values, list):
            for enum_value in enum_values:
                if enum_value is not None:
                    return enum_value

        const_value = schema_property.get("const")
        if const_value is not None:
            return const_value

        property_type = schema_property.get("type") or self._first_json_type(schema_property)
        if property_type == "boolean":
            return False
        if property_type in {"integer", "number"}:
            return 0
        if property_type == "array":
            return []
        if property_type == "object":
            return {}
        return ""

    @classmethod
    def _nested_config_model(
        cls,
        annotation: object,
    ) -> tuple[type[ProviderConfig] | None, bool]:
        """从字段注解中提取嵌套 Provider 配置模型及列表标记。"""
        origin = get_origin(annotation)
        if origin is list:
            item_types = get_args(annotation)
            if not item_types:
                return None, False
            return cls._provider_config_model(item_types[0]), True
        return cls._provider_config_model(annotation), False

    @classmethod
    def _provider_config_model(
        cls,
        annotation: object,
    ) -> type[ProviderConfig] | None:
        """从直接或可选类型注解中提取 Provider 配置模型。"""
        if isinstance(annotation, type) and issubclass(annotation, ProviderConfig):
            return annotation

        origin = get_origin(annotation)
        if origin is Annotated:
            arguments = get_args(annotation)
            return cls._provider_config_model(arguments[0]) if arguments else None
        if origin in {Union, UnionType}:
            for argument in get_args(annotation):
                nested_model = cls._provider_config_model(argument)
                if nested_model is not None:
                    return nested_model
        return None

    @staticmethod
    def _first_json_type(schema_property: dict[str, Any]) -> object:
        """获取 anyOf/oneOf 中第一个非 null JSON 类型。"""
        for key in ("anyOf", "oneOf"):
            variants = schema_property.get(key)
            if not isinstance(variants, list):
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_type = variant.get("type")
                if isinstance(variant_type, str) and variant_type != "null":
                    return variant_type
        return None
