"""Dashboard statistics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import Container

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def stats(container: Container) -> Any:
    """Task totals and execution counters by status."""
    return await container.stats.overview()
