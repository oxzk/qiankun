"""内置 Provider 加载管理器。"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import ClassVar

from app.shared.errors import AppError
from app.provider_plugins.base import BaseProvider, find_single_provider_class


class BuiltinProviderRegistry:
    """内置 Provider 管理器。"""

    DEFAULT_PROVIDER_PACKAGE: ClassVar[str] = "app.provider_plugins.builtin"

    def __init__(self) -> None:
        """初始化 Provider 注册表。"""
        self._providers: dict[str, type[BaseProvider]] = {}

    def load_providers(self, package_name: str = DEFAULT_PROVIDER_PACKAGE) -> list[str]:
        """自动发现并加载内置 Provider。"""
        package = importlib.import_module(package_name)
        package_paths = getattr(package, "__path__", None)
        if package_paths is None:
            raise AppError(f"Provider 包不可加载: {package_name}")

        loaded: dict[str, type[BaseProvider]] = {}
        prefix = f"{package.__name__}."
        for module_info in pkgutil.iter_modules(package_paths, prefix):
            module_short_name = module_info.name.rsplit(".", 1)[-1]
            if module_info.ispkg or self._should_skip_module(
                package.__name__,
                module_info.name,
                module_short_name,
            ):
                continue
            module = importlib.import_module(module_info.name)
            provider_class = self._find_provider_class(module_short_name, module)
            loaded[provider_class.name] = provider_class

        self._providers = loaded
        return self.names()

    def names(self) -> list[str]:
        """返回已加载 Provider 名称。"""
        return sorted(self._providers)

    def get(self, name: str) -> type[BaseProvider]:
        """获取 Provider 类。"""
        self._ensure_loaded()
        provider_class = self._providers.get(name)
        if provider_class is None:
            raise AppError(f"Provider 不存在: {name}", status_code=404)
        return provider_class

    def create(self, name: str) -> BaseProvider:
        """创建 Provider 实例。"""
        provider_class = self.get(name)
        return provider_class()

    def list_infos(self) -> list[dict[str, object]]:
        """返回 Provider 元信息列表。"""
        self._ensure_loaded()
        return [self._to_info(provider_class) for provider_class in self._providers.values()]

    def get_info(self, name: str) -> dict[str, object]:
        """返回指定 Provider 元信息。"""
        return self._to_info(self.get(name))

    def _ensure_loaded(self) -> None:
        """确保 Provider 已加载。"""
        if not self._providers:
            self.load_providers()

    def _find_provider_class(
        self,
        provider_name: str,
        module: ModuleType,
    ) -> type[BaseProvider]:
        """从模块查找唯一 Provider 类。"""
        return find_single_provider_class(module, module.__name__, label=f"Provider 模块 {provider_name}")

    @staticmethod
    def _should_skip_module(
        root_package_name: str,
        module_name: str,
        module_short_name: str,
    ) -> bool:
        """判断模块是否应跳过 Provider 自动发现。"""
        if module_short_name.startswith("_"):
            return True

        relative_name = module_name.removeprefix(f"{root_package_name}.")
        # base 包只承载 Provider 基础能力, 不参与业务 Provider 扫描。
        return relative_name == "base" or relative_name.startswith("base.")

    @staticmethod
    def _to_info(provider_class: type[BaseProvider]) -> dict[str, object]:
        """转换 Provider 元信息。"""
        return {
            "name": provider_class.name,
            "provider_class": provider_class,
        }


builtin_provider_registry = BuiltinProviderRegistry()
"""全局 Provider 管理器。"""
