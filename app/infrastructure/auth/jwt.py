"""JWT issuance and verification with access/refresh token types."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import jwt

from app.core.config import JWTSettings
from app.core.exceptions import AuthError


class JWTManager:
    """Signs and validates HS256 tokens with a type claim."""

    def __init__(self, settings: JWTSettings) -> None:
        """Keep signing parameters."""
        self.settings = settings

    @staticmethod
    def principal_id(username: str) -> UUID:
        """Stable identifier derived from the username, no users table."""
        return uuid5(NAMESPACE_URL, f"qiankun:{username}")

    def _create(self, username: str, token_type: str, lifetime: timedelta) -> str:
        """Build one token with all standard claims."""
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": str(self.principal_id(username)),
            "username": username,
            "type": token_type,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "jti": uuid5(NAMESPACE_URL, f"{username}:{now.isoformat()}:{token_type}").hex,
        }
        return jwt.encode(claims, self.settings.secret, algorithm=self.settings.algorithm)

    def create_access(self, username: str) -> str:
        """Short-lived access token."""
        minutes = self.settings.access_token_minutes
        return self._create(username, "access", timedelta(minutes=minutes))

    def create_refresh(self, username: str) -> str:
        """Long-lived refresh token."""
        return self._create(username, "refresh", timedelta(days=self.settings.refresh_token_days))

    def decode(self, token: str, *, expect_refresh: bool = False) -> dict[str, Any]:
        """Validate all standard claims and the token type."""
        try:
            claims = jwt.decode(
                token,
                self.settings.secret,
                algorithms=[self.settings.algorithm],
                options={"require": ["exp", "iat", "nbf", "sub", "type"]},
            )
        except jwt.PyJWTError as error:
            raise AuthError("Invalid token") from error
        expected = "refresh" if expect_refresh else "access"
        if claims.get("type") != expected:
            raise AuthError("Wrong token type")
        if not claims.get("username"):
            raise AuthError("Token missing username")
        return claims
