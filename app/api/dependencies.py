"""Typed FastAPI dependencies for containers, users and pagination."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query, Request

from app.core.exceptions import AuthError


def get_container(request: Request) -> Any:
    """Read the application container installed by the lifespan."""
    return request.app.state.container


Container = Annotated[Any, Depends(get_container)]


class Principal:
    """Identity derived from the JWT, no users table involved."""

    def __init__(self, id: UUID, username: str, token_type: str) -> None:  # noqa: A002
        """Store claims the middleware already verified."""
        self.id = id
        self.username = username
        self.token_type = token_type


def get_current_user(request: Request) -> Principal:
    """Return the principal placed by the JWT middleware."""
    user = getattr(request.state, "user", None)
    if not isinstance(user, Principal):
        raise AuthError("Authentication required")
    return user


CurrentUser = Annotated[Principal, Depends(get_current_user)]

PageNumber = Annotated[int, Query(ge=1, description="One-based page number")]
PageSize = Annotated[int, Query(ge=1, le=100, description="Items per page")]
