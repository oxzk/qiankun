"""Dependency management request schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DependencyInstallRequest(BaseModel):
    """Packages to install, expressed as PEP 508 specs."""

    model_config = ConfigDict(extra="forbid")

    packages: list[str] = Field(min_length=1, max_length=50)
