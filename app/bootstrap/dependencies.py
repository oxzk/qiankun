"""FastAPI 依赖入口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.bootstrap.container import ApplicationContainer
from app.shared.errors import AppError
from app.services.auth.auth_service import AuthService
from app.services.backups.backup_service import BackupService
from app.services.executions.execution_query_service import ExecutionQueryService
from app.services.notifications.notification_channel_service import NotificationChannelService
from app.services.providers.provider_catalog_service import ProviderCatalogService
from app.services.providers.provider_config_service import ProviderConfigService
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.services.providers.provider_sync_service import ProviderSyncService
from app.services.stats.stats_service import StatsService
from app.services.tasks.task_service import TaskService


def get_services(request: Request) -> ApplicationContainer:
    """返回应用服务容器。"""
    return request.app.state.services


def get_current_user(request: Request) -> str:
    """返回当前已认证用户名。"""
    user = getattr(request.state, "user", None)
    if user is None:
        raise AppError("未登录", status_code=401)
    return user


def get_auth_service(request: Request) -> AuthService:
    """返回认证服务。"""
    return get_services(request).auth_service


def get_backup_service(request: Request) -> BackupService:
    """返回数据备份服务。"""
    return get_services(request).backup_service


def get_task_service(request: Request) -> TaskService:
    """返回任务服务。"""
    return get_services(request).task_services.service


def get_provider_service(request: Request) -> ProviderCatalogService:
    """返回 Provider 服务。"""
    return get_services(request).provider_services.catalog


def get_provider_config_service(request: Request) -> ProviderConfigService:
    """返回 Provider 配置校验服务。"""
    return get_services(request).provider_services.config


def get_provider_execution_service(request: Request) -> ProviderExecutionService:
    """返回 Provider 执行服务。"""
    return get_services(request).provider_services.execution


def get_provider_sync_service(request: Request) -> ProviderSyncService:
    """返回 Provider 同步服务。"""
    return get_services(request).provider_services.sync


def get_execution_query_service(request: Request) -> ExecutionQueryService:
    """返回执行记录查询服务。"""
    return get_services(request).execution_services.query


def get_notification_service(request: Request) -> NotificationChannelService:
    """返回通知渠道服务。"""
    return get_services(request).notification_services.channel


def get_stats_service(request: Request) -> StatsService:
    """返回统计服务。"""
    return get_services(request).stats_service


CurrentUserDep = Annotated[str, Depends(get_current_user)]
"""当前已认证用户名依赖。"""
