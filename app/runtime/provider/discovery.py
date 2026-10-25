"""Discover provider classes by walking the app.providers package."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from dataclasses import dataclass, field

from app.runtime.provider.base import BaseProvider
from app.runtime.provider.models import ProviderConfig

PROVIDERS_PACKAGE = "app.providers"
"""Package scanned for provider plugins."""

RESERVED_DIRECTORIES: frozenset[str] = frozenset({"shared"})
"""Directories inside the providers package that never hold a provider."""

_PROVIDER_NAME = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
"""Provider directory and name pattern."""


@dataclass(frozen=True)
class DiscoveredProvider:
    """One provider directory with its compiled class or validation problems."""

    directory: str
    provider_type: type[BaseProvider] | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """A provider is usable only when it compiled without issues."""
        return self.provider_type is not None and not self.issues


def discover_providers(package_name: str = PROVIDERS_PACKAGE) -> list[DiscoveredProvider]:
    """Walk provider directories and report a result for every one of them.

    Never raises for a broken provider: the problem is recorded on that
    provider so the rest still load and the API can report it.
    """
    package = importlib.import_module(package_name)
    discovered: list[DiscoveredProvider] = []
    for info in pkgutil.iter_modules(package.__path__):
        if not info.ispkg:
            continue
        directory = info.name
        if directory in RESERVED_DIRECTORIES:
            continue
        discovered.append(_inspect_directory(package_name, directory))
    return discovered


def _inspect_directory(package_name: str, directory: str) -> DiscoveredProvider:
    """Import one provider module and validate its declaration."""
    issues: list[str] = []
    if not _PROVIDER_NAME.fullmatch(directory):
        issues.append(
            "目录名必须匹配 ^[a-z][a-z0-9_]{2,63}$ (小写字母开头, 允许数字和下划线)"
        )

    module_name = f"{package_name}.{directory}.main"
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        issues.append(f"导入 main.py 失败: {type(error).__name__}: {error}")
        return DiscoveredProvider(directory, None, issues)

    candidates = [
        candidate
        for _, candidate in inspect.getmembers(module, inspect.isclass)
        if candidate.__module__ == module.__name__
        and issubclass(candidate, BaseProvider)
        and candidate is not BaseProvider
        and not inspect.isabstract(candidate)
    ]
    if not candidates:
        issues.append("main.py 中未找到 BaseProvider 的具体子类")
        return DiscoveredProvider(directory, None, issues)
    if len(candidates) > 1:
        names = ", ".join(sorted(candidate.__name__ for candidate in candidates))
        issues.append(f"main.py 中只能定义一个 Provider 类, 实际有: {names}")
        return DiscoveredProvider(directory, None, issues)

    provider_type = candidates[0]
    declared = getattr(provider_type, "name", "")
    if declared != directory:
        issues.append(f"Provider name '{declared}' 必须与目录名 '{directory}' 一致")

    config_schema = getattr(provider_type, "config_schema", None)
    if config_schema is None or not (
        inspect.isclass(config_schema) and issubclass(config_schema, ProviderConfig)
    ):
        issues.append("必须声明 config_schema 且继承 ProviderConfig")

    unknown = set(provider_type.capabilities) - {"browser"}
    if unknown:
        issues.append(f"未知能力: {sorted(unknown)}, 仅支持 browser")

    return DiscoveredProvider(directory, provider_type, issues)
