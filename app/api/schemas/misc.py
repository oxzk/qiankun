"""Provider, auth and system setting schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.schemas.response import ResponseModel


class ProviderConfigValidate(BaseModel):
    """Payload for /providers/{name}/validate-config."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] = Field(default_factory=dict)


class ProviderTestRun(BaseModel):
    """Payload for /providers/{name}/test-run."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=60, gt=0, le=600)


class LoginRequest(BaseModel):
    """Credentials for /auth/login."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=200)


class TokenPair(ResponseModel):
    """Issued tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh token submission."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password rotation payload."""

    model_config = ConfigDict(extra="forbid")

    old_password: SecretStr
    new_password: SecretStr = Field(min_length=8, max_length=200)


class MeResponse(ResponseModel):
    """Current principal."""

    id: str
    username: str


class SystemSettingPut(BaseModel):
    """Payload for PUT /system-settings/{scope}/{key}."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["object", "string", "integer", "boolean", "array"]
    value: Any
    enabled: bool = True
    description: str = ""


class SystemSettingResponse(ResponseModel):
    """Redacted serialization of one settings row."""

    scope: str
    key: str
    type: str
    value: Any
    enabled: bool
    description: str
    created_at: datetime
    updated_at: datetime
    restart_required: bool = False
