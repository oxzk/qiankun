"""认证业务服务。"""

from __future__ import annotations

from app.config.settings import settings
from app.infrastructure.database.models.user import User
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.infrastructure.security.password_hasher import PasswordHasher
from app.infrastructure.security.token_service import TokenService
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.services.auth.results import TokenResult
from app.shared.errors import AppError


class AuthService:
    """用户认证业务服务。"""

    def __init__(
        self,
        password_hasher: PasswordHasher | None = None,
        token_service: TokenService | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化认证业务服务依赖。"""
        self._password_hasher = password_hasher or PasswordHasher()
        self._token_service = token_service or TokenService()
        self._uow_factory = uow_factory

    async def login(self, payload: LoginRequest) -> TokenResult:
        """校验用户名密码并签发访问令牌。"""
        user = await self.get_user_by_username(payload.username)
        password_ok = False
        if user is not None:
            password_ok = await self._password_hasher.averify_password(
                payload.password,
                user.password,
            )
        if user is None or not password_ok:
            raise AppError("用户名或密码错误", status_code=401)

        token = self._token_service.create_access_token(user.username)
        return TokenResult(
            access_token=token,
            expires_in=settings.jwt_expire_hours * 3600,
            user=user,
        )

    async def get_user_by_username(self, username: str) -> User | None:
        """按用户名查询用户。"""
        async with self._uow_factory() as uow:
            return await uow.users.get_by_username(username)

    async def change_password(self, username: str, payload: ChangePasswordRequest) -> None:
        """修改管理员密码。"""
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_username(username)
            if user is None:
                raise AppError("用户不存在", status_code=404)
            if not await self._password_hasher.averify_password(
                payload.old_password,
                user.password,
            ):
                raise AppError("旧密码错误", status_code=400)
            user.password = await self._password_hasher.ahash_password(payload.new_password)
            await uow.users.update(user)
            await uow.commit()
