"""健康检查 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from app import __VERSION__
from app.config.settings import settings
from app.schemas.responses import APIResponse

router = APIRouter(tags=["health"])
"""健康检查路由。"""


@router.get("/health", response_model=APIResponse[dict[str, str]])
async def health() -> APIResponse[dict[str, str]]:
    """返回服务健康状态。"""
    return {
        "name": settings.app_name,
        "version": __VERSION__,
        "status": "running",
    }
