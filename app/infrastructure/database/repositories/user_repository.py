"""用户仓储模块。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.user import User
from app.infrastructure.database.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问类。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化用户仓储。"""
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> User | None:
        """按用户名查询用户。"""
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def exists_by_username(self, username: str) -> bool:
        """判断用户名是否存在。"""
        result = await self.session.execute(select(User.id).where(User.username == username))
        return result.scalar_one_or_none() is not None
