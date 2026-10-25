"""Probe provider configuration: check kinds, accounts and URL helpers."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyUrl, Field, ValidationInfo, field_validator, model_validator

from app.runtime.provider.models import ProviderConfig

ProbeKind = Literal["HTTP", "Redis", "MySQL", "PostgreSQL", "RabbitMQ", "MongoDB"]
"""Connectivity check kinds."""

ALLOWED_SCHEMES: dict[ProbeKind, set[str]] = {
    "HTTP": {"http", "https"},
    "Redis": {"redis", "rediss"},
    "MySQL": {"mysql"},
    "PostgreSQL": {"pg", "postgres", "postgresql"},
    "RabbitMQ": {"amqp", "amqps"},
    "MongoDB": {"mongodb", "mongodb+srv"},
}
"""URL schemes accepted per check kind."""


class ProbeAccount(ProviderConfig):
    """One probe target."""

    name: str = Field(description="账号标识")
    url: AnyUrl = Field(description="检测地址")

    @field_validator("name")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank identifiers."""
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return normalized


class ProbeConfig(ProviderConfig):
    """Connectivity check configuration."""

    kind: ProbeKind = Field(default="HTTP", description="检测类型")
    accounts: list[ProbeAccount] = Field(default_factory=list, description="检测账号列表")
    timeout_seconds: float = Field(default=5.0, gt=0, le=60, description="超时秒数")

    @model_validator(mode="after")
    def validate_target(self) -> ProbeConfig:
        """Require accounts, matching schemes and explicit ports for non-HTTP kinds."""
        if not self.accounts:
            raise ValueError(f"{self.kind} 检测必须配置 accounts")
        for account in self.accounts:
            scheme = account.url.scheme.lower()
            if scheme not in ALLOWED_SCHEMES[self.kind]:
                raise ValueError(f"{self.kind} 检测不支持 {scheme} 协议")
            port_missing = self._target_port(account.url) is None
            if self.kind != "HTTP" and scheme != "mongodb+srv" and port_missing:
                raise ValueError(f"{self.kind} 检测 URL 必须包含端口")
        return self

    @staticmethod
    def _target_host(target_url: AnyUrl) -> str:
        """Host of the target URL."""
        host = urlsplit(str(target_url)).hostname
        if not host:
            raise ValueError("检测 URL 必须包含主机")
        return host

    @staticmethod
    def _target_port(target_url: AnyUrl) -> int | None:
        """Port of the target URL, None when absent."""
        return urlsplit(str(target_url)).port

    @staticmethod
    def _display_url(target_url: AnyUrl) -> str:
        """URL with the password masked, safe for logs and result data."""
        parsed = urlsplit(str(target_url))
        if parsed.password is None:
            return str(target_url)

        host = parsed.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"

        username = parsed.username or ""
        userinfo = f"{username}:***" if username else ":***"
        return urlunsplit(
            (parsed.scheme, f"{userinfo}@{host}", parsed.path, parsed.query, parsed.fragment)
        )
