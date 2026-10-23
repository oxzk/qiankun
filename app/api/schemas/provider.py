"""Provider management request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.response import ResponseModel


class ProviderResponse(ResponseModel):
    """Catalog entry; invalid providers carry their issues."""

    name: str
    valid: bool
    issues: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)


class ProviderDetail(ProviderResponse):
    """Catalog entry including the provider source."""

    code: str = ""


class ProviderCreate(BaseModel):
    """Create payload: the name must match the directory name."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]{2,63}$")
    code: str = Field(min_length=1)


class ProviderUpdate(BaseModel):
    """Update payload containing the replacement source."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)


class ProviderValidateRequest(BaseModel):
    """Code submitted for validation only."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)


class ProviderValidateResult(ResponseModel):
    """Validation outcome with human readable issues."""

    valid: bool
    issues: list[str] = Field(default_factory=list)
