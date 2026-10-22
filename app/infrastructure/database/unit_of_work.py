"""工作单元模块。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import db
from app.infrastructure.database.repositories.execution_repository import ExecutionRepository
from app.infrastructure.database.repositories.notification_repository import NotificationRepository
from app.infrastructure.database.repositories.provider_repository import ProviderRepository
from app.infrastructure.database.repositories.task_repository import TaskRepository
from app.infrastructure.database.repositories.user_repository import UserRepository

ResultT = TypeVar("ResultT")
"""工作单元操作结果类型。"""


class UnitOfWork:
    """管理单个业务用例内的数据库会话和仓储实例。"""

    def __init__(self) -> None:
        """初始化工作单元状态。"""
        self._session_context: AbstractAsyncContextManager[AsyncSession] | None = None
        self.session: AsyncSession | None = None
        self.tasks: TaskRepository
        self.providers: ProviderRepository
        self.executions: ExecutionRepository
        self.notifications: NotificationRepository
        self.users: UserRepository

    async def __aenter__(self) -> "UnitOfWork":
        """打开数据库会话并初始化仓储。"""
        self._session_context = db.get_session()
        self.session = await self._session_context.__aenter__()
        self.tasks = TaskRepository(self.session)
        self.providers = ProviderRepository(self.session)
        self.executions = ExecutionRepository(self.session)
        self.notifications = NotificationRepository(self.session)
        self.users = UserRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """关闭数据库会话并沿用数据库上下文事务处理。"""
        if self._session_context is None:
            return
        await self._session_context.__aexit__(exc_type, exc, traceback)
        self._session_context = None
        self.session = None

    async def commit(self) -> None:
        """显式提交当前工作单元事务。"""
        if self.session is None:
            raise RuntimeError("工作单元尚未打开")
        await self.session.commit()

    async def rollback(self) -> None:
        """显式回滚当前工作单元事务。"""
        if self.session is None:
            raise RuntimeError("工作单元尚未打开")
        await self.session.rollback()


async def commit_on_success(
    uow_factory: "UnitOfWorkFactory",
    operation: Callable[[UnitOfWork], Awaitable[ResultT]],
) -> ResultT:
    """执行写操作并在成功后提交事务。"""
    async with uow_factory() as uow:
        try:
            result = await operation(uow)
        except Exception:
            await uow.rollback()
            raise
        await uow.commit()
        return result


class UnitOfWorkFactory(Protocol):
    """工作单元工厂协议。"""

    def __call__(self) -> UnitOfWork:
        """创建新的工作单元。"""
        ...
