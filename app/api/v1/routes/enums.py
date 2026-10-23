"""Enum listing for frontend rendering."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.schemas.response import SuccessResponse
from app.runtime.enums import ENUM_REGISTRY

router = APIRouter(prefix="/enums", tags=["enums"])


@router.get("", response_model=SuccessResponse[dict[str, list[dict[str, int | str]]]])
async def list_enums() -> Any:
    """All domain enums with integer values and names."""
    return ENUM_REGISTRY
