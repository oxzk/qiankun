"""Unit of Work owning the transaction and the repository set."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.repositories.system_setting import SystemSettingRepository
from app.infrastructure.database.repositories.task import TaskRepository
from app.infrastructure.database.repositories.task_execution import TaskExecutionRepository


class UnitOfWork:
    """One transaction boundary; repositories share its session."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Store the factory; resources are created on entry."""
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> UnitOfWork:
        """Open a session and expose repositories on attributes."""
        if self._session is not None:
            raise RuntimeError("UnitOfWork cannot be entered twice")
        self._session = self._session_factory()
        self.tasks = TaskRepository(self._session)
        self.task_executions = TaskExecutionRepository(self._session)
        self.system_settings = SystemSettingRepository(self._session)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Commit on success, rollback on any failure, always close."""
        try:
            if exc_type is None and self._session is not None:
                await self._session.commit()
        except Exception:
            if self._session is not None:
                await self._session.rollback()
            raise
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    def session(self) -> Any:
        """Expose the raw session for repository internals and tests."""
        return self._session
