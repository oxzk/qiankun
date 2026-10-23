"""Authentication: login against system_settings credentials, JWT refresh."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import AuthError, NotFoundError
from app.infrastructure.auth.jwt import JWTManager
from app.infrastructure.auth.password import hash_password, secrets_equal, verify_password


class AuthService:
    """Issues tokens from credentials stored in system_settings auth/admin."""

    def __init__(self, uow_factory: Any, jwt: JWTManager) -> None:
        """Keep the UoW factory and JWT manager."""
        self.uow_factory = uow_factory
        self.jwt = jwt

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Verify credentials with timing-safe comparisons; issue both tokens."""
        credentials = await self._credentials()
        if credentials is None:
            raise AuthError("管理员凭证未配置")
        stored_username = str(credentials.get("username", ""))
        stored_hash = str(credentials.get("password", ""))
        if not stored_username or not stored_hash:
            raise AuthError("管理员凭证未配置")
        username_ok = secrets_equal(username, stored_username)
        password_ok = verify_password(password, stored_hash)
        if not (username_ok and password_ok):
            raise AuthError("用户名或密码错误")
        return {
            "access_token": self.jwt.create_access(username),
            "refresh_token": self.jwt.create_refresh(username),
            "token_type": "bearer",
        }

    async def refresh(self, username: str) -> dict[str, Any]:
        """Issue a new access token after the refresh token was validated."""
        credentials = await self._credentials()
        if credentials is None or not credentials.get("enabled", True):
            raise AuthError("管理员凭证已失效")
        return {
            "access_token": self.jwt.create_access(username),
            "refresh_token": self.jwt.create_refresh(username),
            "token_type": "bearer",
        }

    async def me(self, username: str, principal_id: str) -> dict[str, Any]:
        """Identity payload for /auth/me."""
        return {"id": principal_id, "username": username}

    async def change_password(self, username: str, old_password: str, new_password: str) -> None:
        """Rotate the stored credential hash."""
        if len(new_password) < 8:
            raise AuthError("新密码至少 8 个字符")
        credentials = await self._credentials()
        if credentials is None:
            raise AuthError("管理员凭证未配置")
        if not verify_password(old_password, str(credentials.get("password", ""))):
            raise AuthError("旧密码错误")
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key("auth", "admin")
            if row is None:
                raise NotFoundError("管理员凭证未配置")
            await uow.system_settings.update(
                row, {"value": {"username": username, "password": hash_password(new_password)}}
            )

    async def _credentials(self) -> dict[str, Any] | None:
        """Load the auth/admin row value."""
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key("auth", "admin")
        if row is None:
            return None
        return dict(row.value or {})
