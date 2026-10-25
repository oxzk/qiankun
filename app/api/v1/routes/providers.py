"""Provider catalog, source management and trial execution endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import Container
from app.api.schemas.misc import ProviderConfigValidate, ProviderTestRun
from app.api.schemas.provider import (
    ProviderCreate,
    ProviderDetail,
    ProviderResponse,
    ProviderUpdate,
    ProviderValidateRequest,
    ProviderValidateResult,
)
from app.api.schemas.response import SuccessResponse

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=SuccessResponse[list[ProviderResponse]])
async def list_providers(container: Container) -> Any:
    """All providers including invalid ones, with their load issues."""
    return container.providers_service.list()


@router.post("/validate", response_model=SuccessResponse[ProviderValidateResult])
async def validate_code(payload: ProviderValidateRequest, container: Container) -> Any:
    """Compile provider code without persisting it."""
    return container.providers_service.validate(payload.code)


@router.post("/reload")
async def reload_providers(container: Container) -> Any:
    """Rescan the providers package and hot-swap the registry."""
    return container.providers_service.reload()


@router.post("", response_model=SuccessResponse[ProviderDetail])
async def create_provider(payload: ProviderCreate, container: Container) -> Any:
    """Create a provider by writing providers/<name>/main.py."""
    return container.providers_service.create(payload.name, payload.code)


@router.get("/{name}", response_model=SuccessResponse[ProviderDetail])
async def get_provider(name: str, container: Container) -> Any:
    """One provider descriptor with its source."""
    return container.providers_service.get(name)


@router.put("/{name}", response_model=SuccessResponse[ProviderDetail])
async def update_provider(name: str, payload: ProviderUpdate, container: Container) -> Any:
    """Replace provider source and reload the registry atomically."""
    return container.providers_service.update(name, payload.code)


@router.delete("/{name}")
async def delete_provider(name: str, container: Container) -> Any:
    """Delete a provider; refused while tasks still reference it."""
    await container.providers_service.delete(name)
    return {"success": True, "data": {"deleted": name}}


@router.post("/{name}/validate-config")
async def validate_config(
    name: str, payload: ProviderConfigValidate, container: Container
) -> Any:
    """Validate a task config against the provider schema."""
    return container.providers_service.validate_config(name, payload.config)


@router.post("/{name}/test-run")
async def test_run(name: str, payload: ProviderTestRun, container: Container) -> Any:
    """Execute the provider once with a synthetic context."""
    return await container.providers_service.test_run(
        name, payload.config, payload.timeout
    )
