"""Dependency manifest stored in system_settings plus install orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.exceptions import ConflictError, ValidationError
from app.core.utils import utc_now
from app.infrastructure.plugins import dependencies
from app.infrastructure.plugins.dependencies import DependencyError

SCOPE = "dependencies"
"""Scope holding the manifest and last install state."""

MANIFEST_KEY = "extra"
"""Key whose value holds ``{"packages": [...]}``."""

STATE_KEY = "state"
"""Key whose value holds the last install result, never the source of truth."""


class DependencyService:
    """Reads and mutates the dependency manifest, then installs via uv."""

    def __init__(self, uow_factory: Any, registry: Any) -> None:
        """Keep the UoW factory and the registry reloaded after installs."""
        self.uow_factory = uow_factory
        self.registry = registry
        self._lock = asyncio.Lock()

    async def describe(self) -> dict[str, Any]:
        """Manifest, installed packages, drift and the protected list."""
        snapshot = dependencies.describe(await self._packages())
        snapshot["state"] = await self._state()
        return snapshot

    async def add(self, specs: list[str]) -> dict[str, Any]:
        """Install packages, then record them in the manifest."""
        cleaned = [spec.strip() for spec in specs if spec.strip()]
        if not cleaned:
            raise ValidationError("至少提供一个依赖")
        problems = dependencies.validate_specs(cleaned)
        if problems:
            raise ValidationError("依赖校验失败", {"problems": problems})
        async with self._lock:
            current = await self._packages()
            merged = _merge(current, cleaned)
            before = dependencies.installed_packages()
            try:
                await dependencies.install(cleaned)
            except DependencyError as error:
                await self._save_state(
                    {"last_error": str(error), "last_sync_at": utc_now().isoformat()}
                )
                raise ValidationError(f"安装失败: {error}") from error
            await self._write_manifest(merged)
            reloaded = self._reload_registry()
            restart_required = _changed_versions(before, cleaned)
            await self._save_state(
                {
                    "last_error": "",
                    "last_sync_at": utc_now().isoformat(),
                    "restart_required": restart_required,
                }
            )
            snapshot = dependencies.describe(merged)
            snapshot["state"] = await self._state()
            snapshot["reloaded_providers"] = reloaded
            snapshot["restart_required"] = restart_required
            return snapshot

    async def remove(self, package: str) -> dict[str, Any]:
        """Uninstall one package and drop it from the manifest."""
        spec_name = dependencies.package_name(package)
        if not spec_name:
            raise ValidationError("依赖名称不能为空")
        if spec_name in {dependencies.normalize(p) for p in dependencies.PROTECTED_PACKAGES}:
            raise ConflictError(f"{package} 属于核心依赖, 不允许卸载")
        async with self._lock:
            current = await self._packages()
            remaining = [
                spec for spec in current if dependencies.package_name(spec) != spec_name
            ]
            if len(remaining) == len(current):
                raise ValidationError(f"{package} 不在依赖清单中")
            try:
                await dependencies.uninstall([spec_name])
            except DependencyError as error:
                await self._save_state(
                    {"last_error": str(error), "last_sync_at": utc_now().isoformat()}
                )
                raise ValidationError(f"卸载失败: {error}") from error
            await self._write_manifest(remaining)
            reloaded = self._reload_registry()
            await self._save_state(
                {
                    "last_error": "",
                    "last_sync_at": utc_now().isoformat(),
                    "restart_required": [],
                }
            )
            snapshot = dependencies.describe(remaining)
            snapshot["state"] = await self._state()
            snapshot["reloaded_providers"] = reloaded
            return snapshot

    async def sync(self) -> dict[str, Any]:
        """Converge the environment to the stored manifest."""
        async with self._lock:
            current = await self._packages()
            if not current:
                return {"installed": [], "message": "清单为空"}
            problems = dependencies.validate_specs(current)
            if problems:
                await self._save_state(
                    {"last_error": "; ".join(problems), "last_sync_at": utc_now().isoformat()}
                )
                raise ValidationError("清单校验失败", {"problems": problems})
            missing = [
                spec
                for spec in current
                if dependencies.package_name(spec)
                not in dependencies.installed_packages()
            ]
            if not missing:
                return {"installed": [], "message": "依赖已就绪"}
            try:
                output = await dependencies.install(missing)
            except DependencyError as error:
                await self._save_state(
                    {"last_error": str(error), "last_sync_at": utc_now().isoformat()}
                )
                raise ValidationError(f"同步失败: {error}") from error
            reloaded = self._reload_registry()
            await self._save_state(
                {
                    "last_error": "",
                    "last_sync_at": utc_now().isoformat(),
                    "restart_required": [],
                }
            )
            return {
                "installed": missing,
                "output": output[-2000:],
                "reloaded_providers": reloaded,
            }

    async def _packages(self) -> list[str]:
        """Manifest packages from system_settings."""
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key(SCOPE, MANIFEST_KEY)
        if row is None:
            return []
        value = row.value if isinstance(row.value, dict) else {}
        packages = value.get("packages", [])
        return [str(spec) for spec in packages] if isinstance(packages, list) else []

    async def _state(self) -> dict[str, Any]:
        """Last install result stored alongside the manifest."""
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key(SCOPE, STATE_KEY)
        return dict(row.value) if row is not None and isinstance(row.value, dict) else {}

    async def _write_manifest(self, packages: list[str]) -> None:
        """Persist the manifest, creating the row on first use."""
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key(SCOPE, MANIFEST_KEY)
            values = {"type": "object", "value": {"packages": packages}, "enabled": True}
            if row is None:
                await uow.system_settings.add(
                    {
                        "scope": SCOPE,
                        "key": MANIFEST_KEY,
                        "description": "自定义依赖清单",
                        **values,
                    }
                )
            else:
                await uow.system_settings.update(row, values)

    async def _save_state(self, state: dict[str, Any]) -> None:
        """Merge and persist the last install state."""
        merged = {**await self._state(), **state}
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key(SCOPE, STATE_KEY)
            values = {"type": "object", "value": merged, "enabled": True}
            if row is None:
                await uow.system_settings.add(
                    {
                        "scope": SCOPE,
                        "key": STATE_KEY,
                        "description": "最近一次依赖安装结果",
                        **values,
                    }
                )
            else:
                await uow.system_settings.update(row, values)

    def _reload_registry(self) -> list[str]:
        """Rescan providers so new imports become usable immediately."""
        try:
            self.registry.reload()
        except Exception:
            return []
        return self.registry.names()


def _merge(current: list[str], incoming: list[str]) -> list[str]:
    """Merge requirements, letting incoming specs replace the same package."""
    incoming_names = {dependencies.package_name(spec) for spec in incoming}
    kept = [
        spec for spec in current if dependencies.package_name(spec) not in incoming_names
    ]
    return [*kept, *incoming]


def _changed_versions(before: dict[str, str], specs: list[str]) -> list[str]:
    """Packages whose version changed while already imported need a restart."""
    after = dependencies.installed_packages()
    changed: list[str] = []
    for spec in specs:
        name = dependencies.package_name(spec)
        previous = before.get(name)
        current = after.get(name)
        if previous is not None and current is not None and previous != current:
            changed.append(f"{name} {previous} -> {current}")
    return changed
