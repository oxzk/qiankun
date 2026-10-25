"""Grouped pydantic-settings with no project prefix on environment variables."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import NoDecode


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection, read from DATABASE_* variables."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="forbid")

    url: str = Field(..., description="Async SQLAlchemy URL starting with postgresql+asyncpg://")

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str) -> str:
        """Reject URLs that do not use the asyncpg driver."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with postgresql+asyncpg://")
        return value


class JWTSettings(BaseSettings):
    """Token signing parameters, read from JWT_* variables."""

    model_config = SettingsConfigDict(env_prefix="JWT_", extra="forbid")

    secret: str = Field(..., min_length=32, description="Signing secret for HS256 tokens")
    algorithm: str = Field(default="HS256", description="Signing algorithm")
    access_token_minutes: int = Field(
        default=30, ge=1, description="Access token lifetime in minutes"
    )
    refresh_token_days: int = Field(
        default=30, ge=1, description="Refresh token lifetime in days"
    )

    @field_validator("secret")
    @classmethod
    def check_secret(cls, value: str) -> str:
        """Reject the placeholder shipped in the example file."""
        if value == "change-this-secret-at-least-32-characters-long":
            raise ValueError("JWT_SECRET must be changed from the example value")
        return value


class SchedulerSettings(BaseModel):
    """Polling and concurrency knobs of the scheduling loop."""

    interval_seconds: float = Field(default=5, ge=1, description="Database polling interval")
    max_concurrent_tasks: int = Field(
        default=10, ge=1, description="Maximum simultaneously running tasks"
    )


class RuntimeSettings(BaseModel):
    """Defaults applied when a task does not override them."""

    default_timeout: int = Field(
        default=300, ge=1, le=86400, description="Fallback execution timeout"
    )
    cleanup_timeout: int = Field(
        default=30, ge=1, le=600, description="Capability teardown timeout"
    )


class SystemBaseSettings(SchedulerSettings, RuntimeSettings):
    """Flat union of scheduler and runtime knobs persisted in system_settings."""

    model_config = ConfigDict(extra="forbid")


class LoggingSettings(BaseModel):
    """Loguru sink options, hot-reloadable from system_settings."""

    level: str = Field(default="INFO", description="Minimum log level")
    rotation: str = Field(default="100 MB", description="Rotation size with unit")
    retention: str = Field(default="30 days", description="Retention period with unit")
    directory: str = Field(default="logs", description="Log directory, empty disables file output")

    @field_validator("rotation", "retention")
    @classmethod
    def check_units(cls, value: str) -> str:
        """Require a digit followed by a unit such as MB or days."""
        pattern = r"\d+\s*(b|kb|mb|gb|days?|weeks?|hours?)"
        if not re.fullmatch(pattern, value.strip(), re.IGNORECASE):
            raise ValueError("Value must be a number with a unit, e.g. '100 MB' or '30 days'")
        return value


class Settings(BaseSettings):
    """Aggregate startup configuration; nested groups use the __ delimiter."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database: DatabaseSettings = Field(default=..., description="Database connection")
    jwt: JWTSettings = Field(default=..., description="JWT parameters")
    scheduler: SchedulerSettings = Field(default=SchedulerSettings(), description="Scheduler loop")
    runtime: RuntimeSettings = Field(default=RuntimeSettings(), description="Execution defaults")
    logging: LoggingSettings = Field(default=LoggingSettings(), description="Logging defaults")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a comma separated string from environment variables."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def check_credentials(cls, value: list[str]) -> list[str]:
        """Never combine a wildcard with credentialed requests."""
        if "*" in value:
            raise ValueError("CORS_ORIGINS cannot use '*' with credentials")
        return value


def load_settings() -> Settings:
    """Build settings lazily so importing modules never touches the environment."""
    return Settings()
