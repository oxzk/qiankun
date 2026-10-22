"""数据备份 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_backup_service
from app.schemas.backup import BackupInfo
from app.schemas.responses import APIResponse
from app.services.backups.backup_service import BackupService

router = APIRouter(prefix="/backups", tags=["backups"])
"""数据备份路由。"""


@router.get("", response_model=APIResponse[list[BackupInfo]])
async def list_backups(
    service: BackupService = Depends(get_backup_service),
) -> APIResponse[list[BackupInfo]]:
    """查询备份历史。"""
    return await service.list_backups()


@router.post("", response_model=APIResponse[BackupInfo])
async def create_backup(
    service: BackupService = Depends(get_backup_service),
) -> APIResponse[BackupInfo]:
    """创建数据备份。"""
    return await service.create_backup()


@router.post("/{filename}/restore", response_model=APIResponse[bool])
async def restore_backup(
    filename: str,
    service: BackupService = Depends(get_backup_service),
) -> APIResponse[bool]:
    """恢复指定数据备份。"""
    return await service.restore_backup(filename)
