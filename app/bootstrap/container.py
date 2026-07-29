"""应用服务容器。"""

from __future__ import annotations

from app.infrastructure.http.requester import Requester
from app.infrastructure.security.password_hasher import PasswordHasher
from app.infrastructure.security.token_service import TokenService
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.services.auth.auth_service import AuthService
from app.services.backups.backup_service import BackupService
from app.services.executions.composition import build_execution_services
from app.services.notifications.composition import build_notification_services
from app.services.providers.composition import build_provider_services
from app.services.stats.stats_service import StatsService
from app.services.tasks.composition import build_task_services


class ApplicationContainer:
    """应用级服务依赖容器。"""

    def __init__(self) -> None:
        """初始化应用级服务依赖图。"""
        self.uow_factory = UnitOfWork
        self.requester = Requester()
        self.password_hasher = PasswordHasher()
        self.token_service = TokenService()
        self.auth_service = AuthService(
            password_hasher=self.password_hasher,
            token_service=self.token_service,
            uow_factory=self.uow_factory,
        )
        self.backup_service = BackupService(uow_factory=self.uow_factory)
        self.provider_services = build_provider_services(self.uow_factory)
        self.execution_services = build_execution_services(self.uow_factory)
        self.notification_services = build_notification_services(
            self.requester,
            self.uow_factory,
        )
        self.stats_service = StatsService(uow_factory=self.uow_factory)
        self.task_services = build_task_services(
            provider_config=self.provider_services.config,
            provider_execution=self.provider_services.execution,
            execution_lifecycle=self.execution_services.lifecycle,
            notification_dispatch=self.notification_services.dispatch,
            uow_factory=self.uow_factory,
        )

    async def close(self) -> None:
        """关闭服务容器持有的资源。"""
        await self.requester.close()
