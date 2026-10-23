"""Provider catalog, source management, config validation and trial runs."""

from __future__ import annotations

import ast
import asyncio
from typing import Any
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.database.models.task import Task
from app.infrastructure.plugins.store import RESERVED_DIRECTORIES, ProviderStore
from app.runtime.provider.base import BaseProvider
from app.runtime.provider.models import ProviderContext, ProviderResult
from app.runtime.provider.registry import ProviderRegistry


class ProviderService:
    """Provider catalog plus source CRUD, validation and trial execution."""

    def __init__(
        self,
        registry: ProviderRegistry,
        stream: Any,
        store: ProviderStore,
        uow_factory: Any,
    ) -> None:
        """Keep the registry, log stream, source store and UoW factory."""
        self.registry = registry
        self.stream = stream
        self.store = store
        self.uow_factory = uow_factory

    def list(self) -> list[dict[str, Any]]:
        """Every provider present on disk, including ones that failed to load."""
        catalog: list[dict[str, Any]] = []
        for discovered in self.registry.discovered():
            entry: dict[str, Any] = {
                "name": discovered.directory,
                "valid": discovered.valid,
                "issues": list(discovered.issues),
                "capabilities": [],
                "config_schema": {},
            }
            if discovered.provider_type is not None:
                entry.update(self._schema_of(discovered.provider_type))
            catalog.append(entry)
        return sorted(catalog, key=lambda item: str(item["name"]))

    def get(self, name: str) -> dict[str, Any]:
        """One provider descriptor plus its source when it exists."""
        provider_type = self.registry.types().get(name)
        if provider_type is None:
            issues = self.registry.issues.get(name)
            if issues is None:
                raise NotFoundError(f"Provider '{name}' 不存在")
            return {"name": name, "valid": False, "issues": issues, "code": self._safe_read(name)}
        entry: dict[str, Any] = {"name": name, "valid": True, "issues": []}
        entry.update(self._schema_of(provider_type))
        entry["code"] = self._safe_read(name)
        return entry

    def create(self, name: str, code: str) -> dict[str, Any]:
        """Write a new provider and reload the registry."""
        if self.store.exists(name):
            raise ConflictError(f"Provider '{name}' 已存在")
        self.store.write(name, code)
        return self._activate(name)

    def update(self, name: str, code: str) -> dict[str, Any]:
        """Replace the provider source and reload the registry."""
        if not self.store.exists(name):
            raise NotFoundError(f"Provider '{name}' 不存在")
        previous = self.store.read(name)
        self.store.write(name, code)
        try:
            return self._activate(name)
        except Exception:
            self.store.write(name, previous)
            self.registry.load()
            raise

    async def delete(self, name: str) -> None:
        """Remove the provider after checking that no task references it."""
        if name in RESERVED_DIRECTORIES:
            raise ConflictError(f"'{name}' 是保留目录, 不能删除")
        if not self.store.exists(name):
            raise NotFoundError(f"Provider '{name}' 不存在")
        async with self.uow_factory() as uow:
            _, total = await uow.tasks.list(0, 1, Task.provider == name)
            if total:
                raise ConflictError(
                    f"仍有 {total} 个任务引用 Provider '{name}', 请先删除或改用其他 Provider"
                )
        self.store.delete(name)
        self.registry.load()

    def validate(self, code: str) -> dict[str, Any]:
        """Compile the code without persisting anything and report issues."""
        try:
            compile(code, "<provider>", "exec")
        except SyntaxError as error:
            location = f"第 {error.lineno} 行" if error.lineno else "未知位置"
            return {"valid": False, "issues": [f"语法错误 ({location}): {error.msg}"]}
        issues = _static_issues(code)
        return {"valid": not issues, "issues": issues}

    def reload(self) -> dict[str, Any]:
        """Rescan the providers package and report the resulting state."""
        self.registry.reload()
        return {"providers": self.registry.names(), "issues": self.registry.issues}

    def validate_config(self, name: str, config: dict[str, Any]) -> dict[str, Any]:
        """Validate config against the provider schema without executing."""
        provider = self._provider(name)
        try:
            normalized = provider.validate_config(config)
        except Exception as error:
            raise ValidationError(f"配置校验失败: {error}") from error
        return {"valid": True, "normalized": normalized.model_dump(mode="json")}

    async def test_run(
        self, name: str, config: dict[str, Any], timeout: int = 60  # noqa: ASYNC109
    ) -> dict[str, Any]:
        """Execute the provider once with a synthetic context."""
        provider = self._provider(name)
        from uuid import uuid4

        execution_id = uuid4()
        logger = _TrialLogger(execution_id, self.stream)
        ctx = ProviderContext(
            task_id="test-run",
            execution_id=str(execution_id),
            trigger="manual",
            logger=logger,
        )
        try:
            result: ProviderResult = await asyncio.wait_for(
                provider.run(ctx, config, logger), timeout=timeout
            )
        except TimeoutError:
            result = ProviderResult.fail(f"试运行超时: {timeout} 秒")
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "logs": self.stream.collect(execution_id),
        }

    def _activate(self, name: str) -> dict[str, Any]:
        """Reload the registry and verify the new provider loaded cleanly."""
        self.registry.reload()
        issues = self.registry.issues.get(name, [])
        if issues:
            raise ValidationError(f"Provider '{name}' 加载失败", {"issues": issues})
        provider_type = self.registry.types().get(name)
        if provider_type is None:
            raise ValidationError(f"Provider '{name}' 未注册")
        entry: dict[str, Any] = {"name": name, "valid": True, "issues": []}
        entry.update(self._schema_of(provider_type))
        entry["code"] = self._safe_read(name)
        return entry

    def _safe_read(self, name: str) -> str:
        """Read source when present, empty string when not applicable."""
        try:
            return self.store.read(name)
        except (NotFoundError, ValidationError, ConflictError):
            return ""

    def _provider(self, name: str) -> BaseProvider:
        """Instantiate or 404."""
        if name not in self.registry:
            raise NotFoundError(f"Provider '{name}' 不存在")
        return self.registry.get(name)

    def _schema_of(self, provider_type: type[BaseProvider]) -> dict[str, Any]:
        """Capabilities and config JSON schema for one provider class."""
        return {
            "capabilities": sorted(provider_type.capabilities),
            "config_schema": provider_type.config_schema.model_json_schema(),
        }


def _static_issues(code: str) -> list[str]:
    """Structural checks run without importing the module."""
    tree = ast.parse(code)
    provider_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id in {"BaseProvider"}
            or isinstance(base, ast.Attribute) and base.attr in {"BaseProvider"}
            for base in node.bases
        )
    ]
    issues: list[str] = []
    if len(provider_classes) != 1:
        issues.append(
            f"必须恰好定义一个 BaseProvider 子类, 实际有 {len(provider_classes)} 个"
        )
        return issues
    body = provider_classes[0].body
    declared = {
        target.id
        for item in body
        if isinstance(item, (ast.Assign, ast.AnnAssign))
        for target in (item.targets if isinstance(item, ast.Assign) else [item.target])
        if isinstance(target, ast.Name)
    }
    if "name" not in declared:
        issues.append("类属性 name 未声明")
    if "config_schema" not in declared:
        issues.append("类属性 config_schema 未声明")
    return issues


class _TrialLogger:
    """Logger funneling trial-run output into the shared stream."""

    def __init__(self, execution_id: UUID, stream: Any) -> None:
        """Bind the synthetic execution id."""
        self.execution_id = execution_id
        self.stream = stream

    def info(self, message: str, **context: Any) -> None:
        """Info entry."""
        self.stream.publish(self.execution_id, "INFO", message, context)

    def warning(self, message: str, **context: Any) -> None:
        """Warning entry."""
        self.stream.publish(self.execution_id, "WARNING", message, context)

    def error(self, message: str, **context: Any) -> None:
        """Error entry."""
        self.stream.publish(self.execution_id, "ERROR", message, context)
