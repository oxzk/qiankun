"""认证 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.dependencies import CurrentUserDep, get_auth_service
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from app.schemas.responses import APIResponse
from app.services.auth.auth_service import AuthService
from app.shared.errors import AppError

router = APIRouter(prefix="/auth", tags=["auth"])
"""认证路由。"""


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> APIResponse[TokenResponse]:
    """用户登录。"""
    client_key = request.client.host if request.client is not None else None
    return await service.login(payload, client_key=client_key)


@router.get("/me", response_model=APIResponse[UserOut])
async def me(
    current_user: CurrentUserDep,
    service: AuthService = Depends(get_auth_service),
) -> APIResponse[UserOut]:
    """获取当前登录用户。"""
    user = await service.get_user_by_username(current_user)
    if user is None:
        raise AppError("用户不存在", status_code=401)
    return user


@router.post("/change-password", response_model=APIResponse[bool])
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserDep,
    service: AuthService = Depends(get_auth_service),
) -> APIResponse[bool]:
    """修改管理员密码。"""
    await service.change_password(current_user, payload)
    return True
