"""BaseProvider contract and config declaration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import ValidationError

from app.runtime.logger import Logger
from app.runtime.provider.models import ProviderConfig, ProviderContext, ProviderResult


class BaseProvider(ABC):
    """One scheduled job type; subclasses live under app/providers/."""

    name: ClassVar[str]
    """Unique provider identifier matching the tasks.provider column."""

    config_schema: ClassVar[type[ProviderConfig]]
    """Pydantic model validating tasks.config for this provider."""

    capabilities: ClassVar[frozenset[str]] = frozenset()
    """Runtime capabilities required, e.g. {'browser'}."""

    def __init__(self) -> None:
        """Each execution gets a fresh instance, so context lives per instance."""
        self._context: ProviderContext | None = None

    @property
    def context(self) -> ProviderContext:
        """Execution context of the current attempt."""
        if self._context is None:
            raise RuntimeError("ProviderContext 未初始化, 请通过 run() 执行")
        return self._context

    @property
    def logger(self) -> Logger:
        """Logger of the current execution."""
        return self.context.logger

    def log(self, content: str) -> None:
        """Log through the execution logger, the qiankun.1 style entry point."""
        self.logger.info(content)

    @abstractmethod
    async def execute(self, ctx: ProviderContext, config: ProviderConfig) -> ProviderResult:
        """Run one attempt and return the outcome."""
        ...

    def validate_config(self, values: dict[str, Any]) -> ProviderConfig:
        """Validate raw config, raising ValidationError for callers to map."""
        return self.config_schema.model_validate(values)

    async def run(
        self, ctx: ProviderContext, raw_config: dict[str, Any], logger: Logger
    ) -> ProviderResult:
        """Template method: bind context, validate config, execute, normalize failures."""
        del logger  # ctx.logger is the logger providers see
        self._context = ctx
        try:
            try:
                config = self.validate_config(raw_config)
            except ValidationError as error:
                detail = f"配置校验失败: {error.error_count()} 处错误"
                return ProviderResult.fail(detail, _errors(error))
            try:
                return await self.execute(ctx, config)
            except Exception as error:  # noqa: BLE001 - framework boundary
                ctx.logger.error(f"Provider raised: {type(error).__name__}: {error}")
                return ProviderResult.fail(
                    f"Provider raised {type(error).__name__}: {error}"
                )
        finally:
            self._context = None


def _errors(error: ValidationError) -> dict[str, Any]:
    """Compact validation errors for result payloads."""
    return {
        "errors": [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in error.errors()
        ]
    }
