"""Dependency management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import Container
from app.api.schemas.dependency import DependencyInstallRequest
from app.api.schemas.response import SuccessResponse
from app.infrastructure.plugins import dependencies

router = APIRouter(prefix="/dependencies", tags=["dependencies"])


@router.get("", response_model=SuccessResponse[dict[str, Any]])
async def list_dependencies(container: Container) -> Any:
    """Manifest, installed packages, drift and the protected list."""
    return await container.dependencies.describe()


@router.post("", response_model=SuccessResponse[dict[str, Any]])
async def install_dependencies(
    payload: DependencyInstallRequest, container: Container
) -> Any:
    """Install packages into the application environment and reload providers."""
    return await container.dependencies.add(payload.packages)


@router.delete("/{package}", response_model=SuccessResponse[dict[str, Any]])
async def uninstall_dependency(package: str, container: Container) -> Any:
    """Uninstall one package and drop it from the manifest."""
    return await container.dependencies.remove(package)


@router.post("/sync", response_model=SuccessResponse[dict[str, Any]])
async def sync_dependencies(container: Container) -> Any:
    """Install everything listed in the manifest that is missing."""
    return await container.dependencies.sync()


@router.get("/protected", response_model=SuccessResponse[list[str]])
async def protected_dependencies() -> Any:
    """Core packages the dependency API refuses to change."""
    return sorted(dependencies.PROTECTED_PACKAGES)
