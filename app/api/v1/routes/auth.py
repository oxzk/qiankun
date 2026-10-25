"""Authentication endpoints backed by system_settings credentials."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from app.api.dependencies import Container, CurrentUser
from app.api.schemas.misc import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenPair,
)
from app.api.schemas.response import SuccessResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SuccessResponse[TokenPair])
async def login(container: Container, payload: LoginRequest) -> Any:
    """Exchange credentials for a token pair."""
    return await container.auth.login(
        payload.username, payload.password.get_secret_value()
    )


@router.post("/refresh", response_model=SuccessResponse[TokenPair])
async def refresh(container: Container, payload: RefreshRequest) -> Any:
    """Rotate both tokens from a refresh token; middleware validated its type."""
    claims = container.jwt.decode(payload.refresh_token, expect_refresh=True)
    return await container.auth.refresh(str(claims["username"]))


@router.get("/me", response_model=SuccessResponse[MeResponse])
async def me(container: Container, user: CurrentUser) -> Any:
    """Current principal identity."""
    return await container.auth.me(user.username, str(user.id))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    container: Container, user: CurrentUser, payload: ChangePasswordRequest
) -> None:
    """Rotate the administrator password."""
    await container.auth.change_password(
        user.username,
        payload.old_password.get_secret_value(),
        payload.new_password.get_secret_value(),
    )
