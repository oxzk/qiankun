"""Health probe, the only public endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> Any:
    """Liveness for load balancers and monitoring."""
    return {"success": True, "data": {"status": "ok"}}
