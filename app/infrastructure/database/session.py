"""SQLAlchemy 异步数据库连接模块。"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiomysql
from sqlalchemy import TIMESTAMP, event
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.config.settings import settings


class UTCDateTime(TypeDecorator[datetime]):
    """统一按 UTC 读写的数据库时间类型。"""

    impl = TIMESTAMP
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        """写入数据库前统一转换为 UTC naive 时间。"""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        """从数据库读取后统一补充 UTC 时区信息。"""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    """ORM 声明式模型基类。"""


class Database:
    """SQLAlchemy 异步连接管理器。"""

    def __init__(self) -> None:
        """初始化数据库连接状态。"""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """创建数据库连接池。"""
        if self._engine is not None:
            return

        connect_args: dict[str, object] = {
            "charset": "utf8mb4",
            "cursorclass": aiomysql.DictCursor,
        }
        if settings.database_ssl_enabled:
            connect_args["ssl"] = self._create_ssl_context()

        self._engine = create_async_engine(
            self._normalize_database_url(settings.database_url),
            connect_args=connect_args,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=30,
            pool_recycle=1800,
            # 生产断连后应主动探活, 与 debug 无关。
            # pool_pre_ping=True,
            echo=settings.app_debug,
        )
        event.listen(self._engine.sync_engine, "connect", self._set_utc_timezone)
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def close(self) -> None:
        """关闭数据库连接池。"""
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """获取带事务的异步数据库会话。"""
        if self._session_factory is None:
            raise RuntimeError("数据库尚未初始化")
        async with self._session_factory() as session:
            yield session

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """返回异步数据库会话工厂。"""
        if self._session_factory is None:
            raise RuntimeError("数据库尚未初始化")
        return self._session_factory

    def _set_utc_timezone(
        self,
        dbapi_connection: object,
        connection_record: object,
    ) -> None:
        """将数据库连接会话时区固定为 UTC。"""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
        finally:
            cursor.close()

    def _normalize_database_url(self, database_url: str) -> str:
        """规范化数据库连接地址为 SQLAlchemy 异步 MySQL 地址。"""
        normalized = database_url.strip()
        for sync_scheme in ("mysql://", "mysql+pymysql://", "mysql+mysqldb://"):
            if normalized.startswith(sync_scheme):
                return normalized.replace(sync_scheme, "mysql+aiomysql://", 1)
        return normalized

    def _create_ssl_context(self) -> ssl.SSLContext:
        """创建数据库 SSL 上下文。"""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context


db = Database()
"""全局数据库连接管理器。"""
