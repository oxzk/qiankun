"""Browser capability endpoints: catalog and CDP connectivity test."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import Container

router = APIRouter(prefix="/browsers", tags=["browsers"])


@router.get("")
async def list_browsers() -> Any:
    """The only capability is the CDP driver."""
    return [
        {
            "name": "cdp",
            "description": "远程 CDP 浏览器 (system_settings: browser/cdp)",
            "settings": ["endpoint", "token", "enabled"],
        }
    ]


@router.post("/cdp/test")
async def test_cdp(container: Container) -> Any:
    """Attempt a real connection using the current browser/cdp config."""
    from app.infrastructure.browser.cdp import CDPDriver

    config = container.setting("browser", "cdp")
    if not config.get("endpoint"):
        from app.core.exceptions import ValidationError

        raise ValidationError("请先在 system_settings 的 browser/cdp 中配置 endpoint")
    driver = CDPDriver(config)
    result = await driver.test()
    return {
        "success": result.success,
        "message": result.message,
    }
