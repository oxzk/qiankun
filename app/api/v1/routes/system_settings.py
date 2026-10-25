"""System settings endpoints including notification channels and CDP config."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import Container
from app.api.schemas.misc import SystemSettingPut, SystemSettingResponse
from app.api.schemas.pagination import PageResponse
from app.api.schemas.response import SuccessResponse

router = APIRouter(prefix="/system-settings", tags=["system-settings"])


@router.get("", response_model=SuccessResponse[PageResponse[SystemSettingResponse]])
async def list_settings(
    container: Container,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    scope: Literal[
        "auth", "system", "logging", "browser", "notification", "dependencies"
    ]
    | None = None,
) -> Any:
    """Redacted settings, optionally filtered by scope."""
    return await container.system_settings.list(page, page_size, scope)


@router.get("/notification/channels")
async def notification_channels(container: Container) -> Any:
    """Channels available for task notification_config."""
    page = await container.system_settings.list(1, 100, scope="notification")
    return [
        {"key": item["key"], "enabled": item["enabled"], "description": item["description"]}
        for item in page.items
    ]


@router.get("/{scope}/{key}", response_model=SuccessResponse[SystemSettingResponse])
async def get_setting(scope: str, key: str, container: Container) -> Any:
    """One redacted setting."""
    return await container.system_settings.get(scope, key)


@router.put("/{scope}/{key}", response_model=SuccessResponse[SystemSettingResponse])
async def put_setting(scope: str, key: str, payload: SystemSettingPut, container: Container) -> Any:
    """Upsert one setting; secrets echoed as placeholders keep stored values."""
    return await container.system_settings.put(
        scope, key, payload.model_dump()
    )
