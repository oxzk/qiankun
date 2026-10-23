"""Probe provider configuration schema."""

from __future__ import annotations

from pydantic import Field

from app.runtime.provider.models import ProviderConfig


class ProbeConfig(ProviderConfig):
    """Config accepted by the probe provider."""

    url: str = Field(..., min_length=1, description="要访问的 URL")
    keyword: str = Field(default="", description="页面内容中需要出现的关键字, 留空跳过检查")
