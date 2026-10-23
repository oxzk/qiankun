"""Route modules for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    browsers,
    dependencies,
    enums,
    executions,
    health,
    providers,
    stats,
    system_settings,
    tasks,
)

router = APIRouter()
for module in (
    health,
    auth,
    enums,
    providers,
    tasks,
    executions,
    browsers,
    stats,
    system_settings,
    dependencies,
):
    router.include_router(module.router)
