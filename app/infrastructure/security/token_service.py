"""访问令牌基础设施适配器。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config.settings import settings


class TokenService:
    """封装访问令牌签发和解析能力。"""

    JWT_ALGORITHM = "HS256"
    """JWT 签名算法。"""

    def create_access_token(
        self,
        subject: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """创建访问令牌。"""
        expire_delta = expires_delta or timedelta(hours=settings.jwt_expire_hours)
        expire = datetime.now(timezone.utc) + expire_delta
        payload = {"sub": subject, "exp": expire}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=self.JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """解码并校验访问令牌。"""
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[self.JWT_ALGORITHM])
