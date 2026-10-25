"""Async session factory with expire_on_commit disabled."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions keep attributes usable after commit for response serialization."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
