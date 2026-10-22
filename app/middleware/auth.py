"""认证授权中间件。"""

from __future__ import annotations

import jwt
from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config.settings import settings
from app.schemas.responses import APIResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件。"""

    ALWAYS_EXCLUDED_PATHS = {
        "/api/auth/login",
        "/api/health",
    }
    """始终无需认证的 API 路径。"""

    DEBUG_EXCLUDED_PATHS = {
        "/api/openapi.json",
    }
    """仅调试模式下公开的 API 路径。"""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """对受保护请求执行令牌校验。"""
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api") or path in self._excluded_paths():
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header is None or not auth_header.startswith("Bearer "):
            return self._unauthorized("缺少或无效的认证头")

        token = auth_header[len("Bearer ") :].strip()
        token_service = request.app.state.services.token_service
        try:
            payload = token_service.decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return self._unauthorized("令牌已过期")
        except jwt.InvalidTokenError:
            return self._unauthorized("令牌无效")

        username = payload.get("sub")
        if not username:
            return self._unauthorized("令牌无效")

        request.state.user = str(username)
        return await call_next(request)

    def _excluded_paths(self) -> set[str]:
        """返回当前环境无需认证的路径集合。"""
        excluded = set(self.ALWAYS_EXCLUDED_PATHS)
        if settings.app_debug:
            excluded.update(self.DEBUG_EXCLUDED_PATHS)
        return excluded

    @staticmethod
    def _unauthorized(message: str) -> JSONResponse:
        """构建统一格式的 401 响应。"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=jsonable_encoder(APIResponse.fail(message=message)),
            headers={"WWW-Authenticate": "Bearer"},
        )
