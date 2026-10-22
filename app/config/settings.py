"""应用配置定义。"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"
"""不安全的默认 JWT 密钥。"""


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="QianKun", description="应用名称")
    app_debug: bool = Field(default=False, description="是否启用调试模式")
    database_url: str = Field(
        default="mysql://root:password@127.0.0.1:3306/qiankun",
        description="MySQL 连接地址",
    )
    database_ssl_enabled: bool = Field(default=True, description="是否启用数据库 SSL")
    database_pool_size: int = Field(default=5, ge=1, description="数据库连接池大小")
    database_max_overflow: int = Field(default=10, ge=0, description="数据库连接池最大溢出数")
    jwt_secret_key: str = Field(default=DEFAULT_JWT_SECRET, description="JWT 签名密钥")
    jwt_expire_hours: int = Field(default=24, ge=1, description="JWT 有效小时数")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"], description="CORS 来源")
    http_retry_attempts: int = Field(default=3, ge=1, description="HTTP 请求最大尝试次数")
    http_retry_delay_seconds: float = Field(default=0.5, ge=0, description="HTTP 请求重试初始延迟秒数")
    http_retry_backoff: float = Field(default=2.0, ge=1, description="HTTP 请求重试退避倍数")
    backup_dir: str = Field(default="data/backups", description="数据备份目录")
    scheduler_interval_seconds: int = Field(default=5, ge=1, description="调度轮询间隔秒数")
    scheduler_max_concurrent_tasks: int = Field(
        default=10,
        ge=1,
        description="单实例最大并发任务数",
    )
    provider_code_sandbox: bool = Field(
        default=True,
        description="是否启用 Provider 动态代码沙箱",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: object) -> list[str]:
        """规范化 CORS 来源配置。"""
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json

                return [str(item).strip() for item in json.loads(text) if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "Settings":
        """生产环境下拒绝不安全的默认 JWT 密钥。"""
        if not self.app_debug and self.jwt_secret_key.strip() in {"", DEFAULT_JWT_SECRET}:
            raise ValueError(
                "生产环境必须设置强随机 JWT_SECRET_KEY, 禁止使用默认值 change-me-in-production"
            )
        return self


settings = Settings()
"""全局应用配置。"""
