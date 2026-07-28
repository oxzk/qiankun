"""密码哈希基础设施适配器。"""

from __future__ import annotations

import asyncio

import bcrypt


class PasswordHasher:
    """封装密码哈希和校验能力。"""

    def hash_password(self, password: str) -> str:
        """对明文密码进行 bcrypt 哈希。"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """校验明文密码与哈希密码是否匹配。"""
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except (TypeError, ValueError):
            return False

    async def ahash_password(self, password: str) -> str:
        """异步哈希密码, 避免阻塞事件循环。"""
        return await asyncio.to_thread(self.hash_password, password)

    async def averify_password(self, plain_password: str, hashed_password: str) -> bool:
        """异步校验密码, 避免阻塞事件循环。"""
        return await asyncio.to_thread(self.verify_password, plain_password, hashed_password)
