"""Provider registry rebuilt atomically from the providers package."""

from __future__ import annotations

import sys

from app.core.exceptions import ConflictError, NotFoundError
from app.runtime.provider.base import BaseProvider
from app.runtime.provider.discovery import (
    PROVIDERS_PACKAGE,
    RESERVED_DIRECTORIES,
    DiscoveredProvider,
    discover_providers,
)
from app.runtime.provider.models import ProviderFactory

CAPABILITIES_WHITELIST = frozenset({"browser"})


class ProviderRegistry:
    """Name to factory mapping rebuilt atomically on load or reload."""

    def __init__(self) -> None:
        """Start empty; load() fills the registry."""
        self._providers: dict[str, ProviderFactory] = {}
        self.issues: dict[str, list[str]] = {}

    def load(self) -> None:
        """Discover and validate providers, then swap atomically.

        A broken provider is recorded in ``issues`` and skipped; it never
        prevents the remaining providers from loading.
        """
        rebuilt: dict[str, ProviderFactory] = {}
        issues: dict[str, list[str]] = {}
        for discovered in discover_providers():
            if not discovered.valid:
                issues[discovered.directory] = list(discovered.issues)
                continue
            provider_type = discovered.provider_type
            assert provider_type is not None
            if provider_type.name in rebuilt:
                issues[discovered.directory] = [
                    f"Provider name '{provider_type.name}' 与目录 "
                    f"'{_owner(rebuilt, provider_type.name)}' 重复"
                ]
                continue
            rebuilt[provider_type.name] = provider_type
        self._providers = rebuilt
        self.issues = issues

    def reload(self) -> None:
        """Forget imported provider modules and rescan the package."""
        prefix = f"{PROVIDERS_PACKAGE}."
        reserved = {f"{prefix}{name}" for name in RESERVED_DIRECTORIES}
        for module_name in list(sys.modules):
            if not module_name.startswith(prefix) or module_name in reserved:
                continue
            if module_name.startswith(tuple(f"{name}." for name in reserved)):
                continue
            sys.modules.pop(module_name, None)
        self.load()

    def get(self, name: str) -> BaseProvider:
        """Instantiate a fresh provider for one execution."""
        if name not in self._providers:
            raise NotFoundError(f"Provider '{name}' does not exist")
        provider: BaseProvider = self._providers[name]()
        return provider

    def names(self) -> list[str]:
        """Sorted provider names for listing."""
        return sorted(self._providers)

    def types(self) -> dict[str, type[BaseProvider]]:
        """Provider classes for schema introspection."""
        return {
            name: factory
            for name, factory in self._providers.items()
            if isinstance(factory, type)
        }

    def discovered(self) -> list[DiscoveredProvider]:
        """Fresh scan including invalid providers, for the management API."""
        return discover_providers()

    def __contains__(self, name: str) -> bool:
        """Support membership checks from services."""
        return name in self._providers


def _owner(providers: dict[str, ProviderFactory], name: str) -> str:
    """Directory already owning a provider name, used in conflict messages."""
    for directory, factory in providers.items():
        if getattr(factory, "name", None) == name:
            return directory
    return name
