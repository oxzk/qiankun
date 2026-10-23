"""Probe provider: open a page via CDP browser and check its content."""

from __future__ import annotations

from typing import ClassVar

from app.providers.probe.config import ProbeConfig
from app.runtime.provider.base import BaseProvider
from app.runtime.provider.models import ProviderConfig, ProviderContext, ProviderResult


class ProbeProvider(BaseProvider):
    """Visits one URL through the CDP browser and optionally asserts a keyword."""

    name: ClassVar[str] = "probe"
    config_schema: ClassVar[type[ProviderConfig]] = ProbeConfig  # type: ignore[assignment]
    capabilities: ClassVar[frozenset[str]] = frozenset({"browser"})

    async def execute(self, ctx: ProviderContext, config: ProviderConfig) -> ProviderResult:
        """Open the page, log the title, and match the keyword when given."""
        values = ProbeConfig.model_validate(config.model_dump())
        assert ctx.browser is not None, "browser capability missing"
        ctx.logger.info(f"打开页面 {values.url}")
        page = await ctx.browser.new_page()
        try:
            await page.goto(values.url, wait_until="domcontentloaded", timeout=30000)
            title = await page.title()
            content = await page.content()
            ctx.logger.info(f"页面标题: {title}")
            if values.keyword and values.keyword not in content:
                return ProviderResult.fail(f"页面内容未包含关键字: {values.keyword}")
            return ProviderResult.ok(f"页面访问成功: {title}", {"url": values.url, "title": title})
        finally:
            await page.close()
