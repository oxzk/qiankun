from __future__ import annotations

from typing import ClassVar

from curl_cffi import requests
from pydantic import Field, model_validator

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult


class AfraidConfig(ProviderConfig):
    """Afraid Provider 配置。"""

    username: str | None = Field(default=None, description="Afraid.org 账号")
    password: str | None = Field(default=None, description="Afraid.org 密码")

    @model_validator(mode="after")
    def validate_target(self) -> "AfraidConfig":
        """校验 Afraid.org 登录配置。"""
        if self.username is None or not self.username.strip():
            raise ValueError("Afraid.org 账号不能为空")

        if self.password is None or not self.password:
            raise ValueError("Afraid.org 密码不能为空")
        self.username = self.username.strip()
        return self


class AfraidProvider(BaseProvider):
    """Afraid.org FreeDNS 登录检测 Provider。"""

    name = "afraid"
    config_schema = AfraidConfig
    base_url: ClassVar[str] = "https://freedns.afraid.org/zc.php?step=2"

    async def execute(
        self,
        config: ProviderConfig,
    ) -> ProviderResult:
        """执行 Afraid.org 登录检测。"""
        assert isinstance(config, AfraidConfig)
        typed_config = config
        try:
            response = await self._http_request(
                self.base_url,
                data=self._login_payload(typed_config),
                follow_redirects=True,
            )
        except requests.RequestsError as exc:
            self.log(f"Afraid.org 登录请求失败: {exc}")
            return ProviderResult.fail(
                message="Afraid.org 登录请求失败",
                data={"error": str(exc)},
            )

        authenticated = self._is_login_success(response.text, typed_config.username)
        data = {"status_code": response.status_code, "authenticated": authenticated}
        if authenticated:
            self.log(f"Afraid.org 登录成功, 账号 {typed_config.username}")
            return ProviderResult.ok(
                message="Afraid.org 登录成功",
                data=data,
            )
        self.log(
            "Afraid.org 登录失败, 未识别到已登录账号, "
            f"账号 {typed_config.username}"
        )
        return ProviderResult.fail(
            message="Afraid.org 登录失败, 未识别到已登录账号",
            data=data,
        )

    def _login_payload(self, config: AfraidConfig) -> dict[str, str]:
        """构造 Afraid.org 登录表单。"""
        return {
            "username": config.username,
            "password": config.password,
            "submit": "Login",
            "action": "auth",
        }

    def _is_login_success(self, html: str, username: str) -> bool:
        """判断 Afraid.org 登录响应是否包含已登录账号。"""
        return bool(username and username in html)
