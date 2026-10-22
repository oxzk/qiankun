"""统计 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_stats_service
from app.schemas.responses import APIResponse
from app.schemas.stats import StatsOut
from app.services.stats.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])
"""统计路由。"""


@router.get("", response_model=APIResponse[StatsOut])
async def get_stats(
    service: StatsService = Depends(get_stats_service),
) -> APIResponse[StatsOut]:
    """获取系统统计。"""
    return await service.get_stats()
