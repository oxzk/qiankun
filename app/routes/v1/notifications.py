"""通知渠道 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_notification_service
from app.schemas.notification import (
    NotificationCreate,
    NotificationOut,
    NotificationTestRequest,
    NotificationUpdate,
)
from app.routes.dependencies import page_query
from app.routes.response_builders import build_page_response_from_result
from app.schemas.responses import APIResponse, PageResponse
from app.services.common.pagination import PageQuery
from app.services.notifications.notification_channel_service import NotificationChannelService

router = APIRouter(prefix="/notifications", tags=["notifications"])
"""通知渠道路由。"""


@router.get("", response_model=APIResponse[PageResponse[NotificationOut]])
async def list_notifications(
    pagination: PageQuery = Depends(page_query),
    service: NotificationChannelService = Depends(get_notification_service),
) -> APIResponse[PageResponse[NotificationOut]]:
    """分页查询通知渠道。"""
    return build_page_response_from_result(
        await service.list_notifications(pagination.page, pagination.page_size),
    )


@router.post("", response_model=APIResponse[NotificationOut])
async def create_notification(
    payload: NotificationCreate,
    service: NotificationChannelService = Depends(get_notification_service),
) -> APIResponse[NotificationOut]:
    """创建通知渠道。"""
    return await service.create_notification(payload)


@router.put("/{notification_id}", response_model=APIResponse[NotificationOut])
async def update_notification(
    notification_id: int,
    payload: NotificationUpdate,
    service: NotificationChannelService = Depends(get_notification_service),
) -> APIResponse[NotificationOut]:
    """更新通知渠道。"""
    return await service.update_notification(
        notification_id,
        payload,
    )


@router.delete("/{notification_id}", response_model=APIResponse[None])
async def delete_notification(
    notification_id: int,
    service: NotificationChannelService = Depends(get_notification_service),
) -> APIResponse[None]:
    """删除通知渠道。"""
    await service.delete_notification(notification_id)
    return None


@router.post("/{notification_id}/test", response_model=APIResponse[None])
async def test_notification(
    notification_id: int,
    payload: NotificationTestRequest,
    service: NotificationChannelService = Depends(get_notification_service),
) -> APIResponse[None]:
    """测试通知渠道。"""
    await service.test_notification(notification_id, payload)
    return None
