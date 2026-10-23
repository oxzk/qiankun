"""Tests for provider discovery, registry reload and source storage."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.plugins.store import ProviderStore
from app.runtime.provider.discovery import RESERVED_DIRECTORIES, discover_providers
from app.runtime.provider.registry import ProviderRegistry

VALID_PROVIDER = textwrap.dedent(
    '''
    from app.runtime.provider.base import BaseProvider
    from app.runtime.provider.models import ProviderConfig, ProviderResult
    from pydantic import Field

    class DemoConfig(ProviderConfig):
        message: str = Field(default="hello")

    class DemoProvider(BaseProvider):
        name = "%s"
        config_schema = DemoConfig

        async def execute(self, ctx, config):
            self.log(config.message)
            return ProviderResult.ok(config.message)
    '''
)


def test_discovery_skips_reserved_and_reports_issues() -> None:
    """Every provider directory yields a result; reserved names are skipped."""
    discovered = {item.directory: item for item in discover_providers()}
    assert "shared" not in discovered
    assert not any(name in RESERVED_DIRECTORIES for name in discovered)
    for item in discovered.values():
        assert item.valid, f"{item.directory}: {item.issues}"


def test_registry_never_raises_for_broken_provider() -> None:
    """A broken provider is recorded in issues while others still load."""
    registry = ProviderRegistry()
    registry.load()
    assert "probe" in registry.names()
    assert registry.issues == {}


def test_reload_is_idempotent() -> None:
    """Reloading twice keeps the same provider set."""
    registry = ProviderRegistry()
    registry.load()
    first = registry.names()
    registry.reload()
    assert registry.names() == first


def test_store_rejects_reserved_and_malformed_names(tmp_path: Path) -> None:
    """Reserved directories and bad names never reach the filesystem."""
    store = ProviderStore(tmp_path)
    with pytest.raises(ConflictError):
        store.write("shared", VALID_PROVIDER % "shared")
    with pytest.raises(ValidationError):
        store.write("Bad-Name", VALID_PROVIDER % "Bad-Name")
    with pytest.raises(ValidationError):
        store.write("okname", "def broken(:\n")


def test_store_write_read_delete(tmp_path: Path) -> None:
    """Source round-trips through main.py and the directory is removed."""
    store = ProviderStore(tmp_path)
    code = VALID_PROVIDER % "my_provider"
    store.write("my_provider", code)
    assert store.exists("my_provider")
    assert store.read("my_provider") == code
    assert (tmp_path / "my_provider" / "__init__.py").is_file()
    store.delete("my_provider")
    assert not store.exists("my_provider")
    with pytest.raises(NotFoundError):
        store.read("my_provider")
