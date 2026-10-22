"""认证 API 结构。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field



class LoginRequest(BaseModel):
    """登录请求结构。"""

    username: str = Field(min_length=1, max_length=50, description="用户名")
    password: str = Field(min_length=1, description="密码")


class UserOut(BaseModel):
    """用户响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="用户 ID")
    username: str = Field(description="用户名")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class TokenResponse(BaseModel):
    """登录令牌响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="有效秒数")
    user: UserOut = Field(description="当前用户")


class ChangePasswordRequest(BaseModel):
    """修改密码请求结构。"""

    old_password: str = Field(min_length=1, description="旧密码")
    new_password: str = Field(min_length=1, description="新密码")
