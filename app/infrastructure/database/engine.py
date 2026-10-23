"""Async engine with single-instance advisory lock and UTC enforcement."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import DatabaseSettings
from app.core.exceptions import RuntimeInitializationError

ADVISORY_LOCK_KEY = 1634629225
"""Arbitrary constant reserving the database for this application."""


def build_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create the engine with pre-ping and a UTC session timezone."""
    return create_async_engine(
        settings.url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"timezone": "UTC"}},
    )


class Database:
    """Owns the engine and the single-instance lease."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Build the engine without connecting yet."""
        self.engine = build_engine(settings)
        self._locked = False

    async def initialize(self) -> None:
        """Acquire the advisory lock or fail startup."""
        async with self.engine.connect() as connection:
            acquired = await connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            if not acquired.scalar_one():
                raise RuntimeInitializationError(
                    "Another instance is already running against this database"
                )
        self._locked = True

    async def shutdown(self) -> None:
        """Release the lease before disposing pooled connections."""
        if self._locked:
            async with self.engine.connect() as connection:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
                )
            self._locked = False
        await self.engine.dispose()
