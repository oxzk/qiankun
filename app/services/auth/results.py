"""认证服务结果对象。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.database.models.user import User


@dataclass(frozen=True, slots=True)
class TokenResult:
    """登录令牌服务结果。"""

    access_token: str
    expires_in: int
    user: User
    token_type: str = "bearer"
