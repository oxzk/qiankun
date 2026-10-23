"""Provider execution models: context, result and config base."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel

from app.runtime.logger import Logger


class BrowserHandle(Protocol):
    """Browser capability handed to providers declaring it."""

    async def new_page(self) -> Any:
        """Open a new page in the remote browser context."""
        ...


@dataclass(frozen=True)
class ProviderContext:
    """Everything a provider may touch, nothing more."""

    task_id: str
    execution_id: str
    trigger: str
    logger: Logger
    browser: BrowserHandle | None = None


class ProviderConfig(BaseModel):
    """Base class for provider config schemas."""

    model_config = {"extra": "forbid"}


@dataclass(frozen=True)
class ProviderResult:
    """Outcome returned by one provider execution."""

    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str, data: dict[str, Any] | None = None) -> ProviderResult:
        """Build a success result."""
        return cls(True, message, data or {})

    @classmethod
    def fail(cls, message: str, data: dict[str, Any] | None = None) -> ProviderResult:
        """Build a failure result."""
        return cls(False, message, data or {})


ProviderFactory = Callable[[], Any]
"""Registry entry: zero-argument callable returning a BaseProvider instance."""
