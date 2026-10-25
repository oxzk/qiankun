"""Pure ASGI middleware stack, no BaseHTTPMiddleware cancellation loss."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")

_UUID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

PUBLIC_PATHS: frozenset[str] = frozenset({"/api/v1/health", "/api/v1/auth/login"})


class ConfiguredCORSMiddleware:
    """CORS with origins resolved from the container at first request."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the next ASGI app."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Short-circuit preflight, else annotate simple responses only."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = scope["app"].state.container.settings
        origins = settings.cors_origins
        request_origin = Headers(scope=scope).get("origin", "")
        allow_origin = request_origin if request_origin and request_origin in origins else ""
        if not allow_origin:
            await self.app(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            """Attach CORS headers to http.response.start frames."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", allow_origin.encode()))
                headers.append((b"access-control-allow-credentials", b"true"))
                headers.append(
                    (
                        b"access-control-allow-headers",
                        b"authorization, content-type, x-request-id",
                    )
                )
                headers.append((b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE"))
                message = {**message, "headers": headers}
            await send(message)

        if scope["method"] == "OPTIONS":
            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [(b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return
        await self.app(scope, receive, send_with_cors)


class JWTAuthorizationMiddleware:
    """Protect /api/v1 paths with Bearer tokens, whitelist public paths."""

    def __init__(self, app: ASGIApp, verifier: Callable[[str, bool], Awaitable[Any]]) -> None:
        """Bind the token verifier from the application container."""
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate before routing and store the principal on state."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if not path.startswith("/api/v1") or path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        if path == "/api/v1/auth/refresh":
            require_refresh = True
        else:
            require_refresh = False
        authorization = Headers(scope=scope).get("authorization", "")
        if not authorization.startswith("Bearer "):
            await _reject(send)
            return
        token = authorization.removeprefix("Bearer ").strip()
        try:
            user = await self.verifier(token, require_refresh)
        except Exception:
            await _reject(send)
            return
        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)


async def _reject(send: Send) -> None:
    """Emit the unified unauthorized envelope."""
    body = (
        b'{"success":false,"error":{"code":"unauthorized",'
        b'"message":"Missing or invalid credentials","details":null}}'
    )
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestIDMiddleware:
    """Propagate a validated client request id or generate one."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the next ASGI app."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Echo the id on the response and expose it via contextvars."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header_id = Headers(scope=scope).get("x-request-id", "")
        request_id = header_id if _UUID_PATTERN.fullmatch(header_id) else uuid4().hex
        REQUEST_ID.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            """Attach the id header once the response starts."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            if scope.get("_is_response_started"):
                raise
            raise
