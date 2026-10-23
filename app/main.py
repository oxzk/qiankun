"""FastAPI entry point, wiring only what the lifespan assembles."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import (
    ConfiguredCORSMiddleware,
    JWTAuthorizationMiddleware,
    RequestIDMiddleware,
)
from app.application.container import ApplicationContainer
from app.core.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the container before serving, tear it down in reverse."""
    container = await ApplicationContainer.create(load_settings())
    app.state.container = container
    app.state.jwt = container.jwt
    yield
    await container.shutdown()


class _StateVerifier:
    """Callable verifier resolving the JWT manager from app state lazily."""

    def __init__(self) -> None:
        """Start unbound; the lifespan installs the application reference."""
        self._app: Any = None

    def bind(self, app: Any) -> None:
        """Remember the running application."""
        self._app = app

    async def __call__(self, token: str, expect_refresh: bool) -> Any:
        """Decode the token using the live JWT manager."""
        from uuid import UUID

        from app.api.dependencies import Principal
        from app.core.exceptions import AuthError

        jwt_manager = getattr(self._app.state, "jwt", None) if self._app else None
        if jwt_manager is None:
            raise AuthError("Application not ready")
        claims = jwt_manager.decode(token, expect_refresh=expect_refresh)
        return Principal(UUID(claims["sub"]), str(claims["username"]), str(claims["type"]))


_verifier = _StateVerifier()


def create_app() -> FastAPI:
    """Build the application without importing route modules eagerly."""
    app = FastAPI(title="Qiankun", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    # add_middleware wraps in reverse: effective order CORS -> RequestID -> JWT -> router.
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(JWTAuthorizationMiddleware, verifier=_verifier)
    app.add_middleware(ConfiguredCORSMiddleware)
    from app.api.v1.routes import router

    app.include_router(router, prefix="/api/v1")
    _verifier.bind(app)
    return app


app = create_app()
