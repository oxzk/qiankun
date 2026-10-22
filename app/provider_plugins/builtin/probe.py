"""连通性检测 Provider。"""

from __future__ import annotations

import importlib
import ssl
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, Literal
from urllib.parse import unquote, urlsplit, urlunsplit
from uuid import uuid4

from curl_cffi import requests
from pydantic import AnyUrl, Field, ValidationInfo, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult

ProbeKind = Literal["HTTP", "Redis", "MySQL", "PostgreSQL", "RabbitMQ", "MongoDB"]
"""连通性检测类型。"""

ALLOWED_SCHEMES: dict[ProbeKind, set[str]] = {
    "HTTP": {"http", "https"},
    "Redis": {"redis", "rediss"},
    "MySQL": {"mysql"},
    "PostgreSQL": {"pg", "postgres", "postgresql"},
    "RabbitMQ": {"amqp", "amqps"},
    "MongoDB": {"mongodb", "mongodb+srv"},
}
"""各检测类型允许的 URL 协议。"""

REDIS_CHECK_VALUE = "1"
"""Redis 临时写入检测值。"""

HTTP_METHOD = "GET"
"""HTTP 检测固定请求方法。"""

HTTP_EXPECTED_STATUS_MIN = 200
"""HTTP 检测固定最小成功状态码。"""

HTTP_EXPECTED_STATUS_MAX = 399
"""HTTP 检测固定最大成功状态码。"""

MYSQL_ASYNC_SCHEME = "mysql+aiomysql"
"""MySQL SQLAlchemy 异步连接协议。"""


class ProbeAccount(ProviderConfig):
    """连通性检测账号配置。"""

    name: str = Field(description="账号标识")
    url: AnyUrl = Field(description="检测地址")

    @field_validator("name")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """校验必填文本字段。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return normalized


class ProbeConfig(ProviderConfig):
    """连通性检测配置。"""

    kind: ProbeKind = Field(default="HTTP", description="检测类型")
    accounts: list[ProbeAccount] = Field(default_factory=list, description="检测账号列表")
    timeout_seconds: float = Field(default=5.0, gt=0, le=60, description="超时秒数")

    @model_validator(mode="after")
    def validate_target(self) -> "ProbeConfig":
        """校验检测目标配置。"""
        if not self.accounts:
            raise ValueError(f"{self.kind} 检测必须配置 accounts")

        for account in self.accounts:
            scheme = account.url.scheme.lower()
            if scheme not in ALLOWED_SCHEMES[self.kind]:
                raise ValueError(f"{self.kind} 检测不支持 {scheme} 协议")

            target_port = self._target_port(account.url)
            if self.kind != "HTTP" and scheme != "mongodb+srv" and target_port is None:
                raise ValueError(f"{self.kind} 检测 URL 必须包含端口")
        return self

    @property
    def target_host(self) -> str:
        """返回首个目标主机。"""
        return self._target_host(self.accounts[0].url)

    @property
    def target_port(self) -> int | None:
        """返回首个目标端口。"""
        return self._target_port(self.accounts[0].url)

    @property
    def url_username(self) -> str | None:
        """返回首个 URL 用户名。"""
        return self._url_username(self.accounts[0].url)

    @property
    def url_password(self) -> str | None:
        """返回首个 URL 密码。"""
        return self._url_password(self.accounts[0].url)

    @property
    def url_database(self) -> str | None:
        """返回首个 URL 数据库名称。"""
        return self._url_database(self.accounts[0].url)

    @property
    def display_url(self) -> str:
        """返回首个脱敏后的检测地址。"""
        return self._display_url(self.accounts[0].url)

    @staticmethod
    def _target_host(target_url: AnyUrl) -> str:
        """返回指定目标主机。"""
        host = urlsplit(str(target_url)).hostname
        if not host:
            raise ValueError("检测 URL 必须包含主机")
        return host

    @staticmethod
    def _target_port(target_url: AnyUrl) -> int | None:
        """返回指定目标端口。"""
        return urlsplit(str(target_url)).port

    @staticmethod
    def _url_username(target_url: AnyUrl) -> str | None:
        """返回指定 URL 用户名。"""
        username = urlsplit(str(target_url)).username
        if username is None:
            return None
        return unquote(username)

    @staticmethod
    def _url_password(target_url: AnyUrl) -> str | None:
        """返回指定 URL 密码。"""
        password = urlsplit(str(target_url)).password
        if password is None:
            return None
        return unquote(password)

    @staticmethod
    def _url_database(target_url: AnyUrl) -> str | None:
        """返回指定 URL 数据库名称。"""
        path = urlsplit(str(target_url)).path.strip("/")
        if not path:
            return None
        return unquote(path.split("/", 1)[0])

    @staticmethod
    def _display_url(target_url: AnyUrl) -> str:
        """返回指定脱敏后的检测地址。"""
        parsed = urlsplit(str(target_url))
        if parsed.password is None:
            return str(target_url)

        host = parsed.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"

        username = parsed.username or ""
        userinfo = f"{username}:***" if username else ":***"
        return urlunsplit(
            (
                parsed.scheme,
                f"{userinfo}@{host}",
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )




class ProbeProvider(BaseProvider):
    """连通性检测 Provider 实现。"""

    name = "probe"
    config_schema = ProbeConfig

    async def execute(
        self,
        config: ProviderConfig,
    ) -> ProviderResult:
        """执行连通性检测。"""
        assert isinstance(config, ProbeConfig)
        typed_config = config
        if typed_config.kind == "HTTP":
            return await self._check_http(typed_config)
        if typed_config.kind == "Redis":
            return await self._check_redis(typed_config)
        if typed_config.kind == "MySQL":
            return await self._check_mysql(typed_config)
        if typed_config.kind == "PostgreSQL":
            return await self._check_postgresql(typed_config)
        if typed_config.kind == "RabbitMQ":
            return await self._check_rabbitmq(typed_config)
        return await self._check_mongodb(typed_config)

    async def _check_http(self, config: ProbeConfig) -> ProviderResult:
        """检测 HTTP 连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_http_target,
            "HTTP 连通性正常",
            "HTTP 连通性存在异常目标",
        )

    async def _check_http_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 HTTP 目标连通性。"""
        target_url = account.url
        started_at = perf_counter()
        try:
            response = await self._http_request(
                str(target_url),
                method=HTTP_METHOD,
                timeout=config.timeout_seconds,
                raise_for_status=False,
                retry_on_status=False,
            )
        except requests.RequestsError as exc:
            return self._failure(config, account, started_at, str(exc))

        elapsed_ms = self._elapsed_ms(started_at)
        success = HTTP_EXPECTED_STATUS_MIN <= response.status_code <= HTTP_EXPECTED_STATUS_MAX
        data = {
            "kind": config.kind,
            "account": account.name,
            "url": config._display_url(target_url),
            "method": HTTP_METHOD,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        }
        if success:
            self.log(
                f"[{account.name}] HTTP 连通性正常, "
                f"状态码 {response.status_code}, 耗时 {elapsed_ms}ms"
            )
            return ProviderResult.ok(
                message="HTTP 连通性正常",
                data=data,
            )
        self.log(
            f"[{account.name}] HTTP 响应状态码不符合预期, "
            f"期望 {HTTP_EXPECTED_STATUS_MIN}-{HTTP_EXPECTED_STATUS_MAX}, "
            f"实际 {response.status_code}, 耗时 {elapsed_ms}ms"
        )
        return ProviderResult.fail(
            message="HTTP 响应状态码不符合预期",
            data=data,
        )

    async def _check_redis(self, config: ProbeConfig) -> ProviderResult:
        """检测 Redis 连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_redis_target,
            "Redis 连通性正常",
            "Redis 连通性存在异常目标",
        )

    async def _check_redis_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 Redis 目标连通性。"""
        target_url = account.url
        started_at = perf_counter()
        client: Any | None = None
        try:
            redis_asyncio = importlib.import_module("redis.asyncio")
            client = redis_asyncio.from_url(
                str(target_url),
                socket_connect_timeout=config.timeout_seconds,
                socket_timeout=config.timeout_seconds,
                decode_responses=True,
            )
            check_key = f"qiankun:probe:{uuid4().hex}"
            set_response = await client.set(check_key, REDIS_CHECK_VALUE)
            await client.delete(check_key)
        except Exception as exc:
            return self._failure(config, account, started_at, str(exc))
        finally:
            if client is not None:
                await client.aclose()

        data = self._target_data(config, account, started_at)
        if set_response is True or set_response == "OK":
            self.log(f"[{account.name}] Redis 连通性正常, 耗时 {data['elapsed_ms']}ms")
            return ProviderResult.ok(
                message="Redis 连通性正常",
                data=data,
            )
        self.log(
            f"[{account.name}] Redis SET 响应不符合预期, "
            f"期望 True 或 OK, 实际 {set_response!r}, 耗时 {data['elapsed_ms']}ms"
        )
        return ProviderResult.fail(
            message="Redis SET 响应不符合预期",
            data=data,
        )

    async def _check_mysql(self, config: ProbeConfig) -> ProviderResult:
        """检测 MySQL 查询连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_mysql_target,
            "MySQL 连通性正常",
            "MySQL 连通性存在异常目标",
        )

    async def _check_mysql_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 MySQL 目标查询连通性。"""
        target_url = account.url
        started_at = perf_counter()
        engine: Any | None = None
        try:
            engine = create_async_engine(
                self._mysql_connection_url(target_url),
                connect_args={
                    "connect_timeout": config.timeout_seconds,
                    "ssl": self._create_unverified_ssl_context(),
                },
            )
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            return self._failure(config, account, started_at, str(exc))
        finally:
            if engine is not None:
                await engine.dispose()

        self._log_success(config, account, started_at)
        return ProviderResult.ok(
            message="MySQL 连通性正常",
            data=self._target_data(config, account, started_at),
        )

    async def _check_postgresql(self, config: ProbeConfig) -> ProviderResult:
        """检测 PostgreSQL 查询连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_postgresql_target,
            "PostgreSQL 连通性正常",
            "PostgreSQL 连通性存在异常目标",
        )

    async def _check_postgresql_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 PostgreSQL 目标查询连通性。"""
        target_url = account.url
        started_at = perf_counter()
        connection: Any | None = None
        try:
            asyncpg = importlib.import_module("asyncpg")
            connection = await asyncpg.connect(
                str(target_url),
                timeout=config.timeout_seconds,
                ssl=self._create_unverified_ssl_context(),
            )
            await connection.fetchval("SELECT 1")
        except Exception as exc:
            return self._failure(config, account, started_at, str(exc))
        finally:
            if connection is not None:
                await connection.close()

        self._log_success(config, account, started_at)
        return ProviderResult.ok(
            message="PostgreSQL 连通性正常",
            data=self._target_data(config, account, started_at),
        )

    async def _check_rabbitmq(self, config: ProbeConfig) -> ProviderResult:
        """检测 RabbitMQ 连接连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_rabbitmq_target,
            "RabbitMQ 连通性正常",
            "RabbitMQ 连通性存在异常目标",
        )

    async def _check_rabbitmq_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 RabbitMQ 目标的消息生产与消费能力。"""
        target_url = account.url
        started_at = perf_counter()
        connection: Any | None = None
        channel: Any | None = None
        try:
            aio_pika = importlib.import_module("aio_pika")
            connection = await aio_pika.connect_robust(
                str(target_url),
                timeout=config.timeout_seconds,
            )
            channel = await connection.channel()
            queue = await channel.declare_queue(
                exclusive=True,
                auto_delete=True,
                timeout=config.timeout_seconds,
            )
            message_body = f"qiankun-probe:{uuid4().hex}".encode()
            await channel.default_exchange.publish(
                aio_pika.Message(body=message_body),
                routing_key=queue.name,
                timeout=config.timeout_seconds,
            )
            incoming_message = await queue.get(timeout=config.timeout_seconds)
            if incoming_message is None:
                raise RuntimeError("RabbitMQ 未消费到检测消息")
            consumed_body = incoming_message.body
            await incoming_message.ack()
            if consumed_body != message_body:
                raise RuntimeError("RabbitMQ 消费消息与生产消息不一致")
        except Exception as exc:
            return self._failure(config, account, started_at, str(exc))
        finally:
            try:
                if channel is not None:
                    await channel.close()
            finally:
                if connection is not None:
                    await connection.close()

        self._log_success(config, account, started_at)
        return ProviderResult.ok(
            message="RabbitMQ 连通性正常",
            data=self._target_data(config, account, started_at),
        )

    async def _check_mongodb(self, config: ProbeConfig) -> ProviderResult:
        """检测 MongoDB ping 连通性。"""
        return await self._check_multiple_targets(
            config,
            self._check_mongodb_target,
            "MongoDB 连通性正常",
            "MongoDB 连通性存在异常目标",
        )

    async def _check_mongodb_target(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
    ) -> ProviderResult:
        """检测单个 MongoDB 目标 ping 连通性。"""
        target_url = account.url
        started_at = perf_counter()
        client: Any | None = None
        try:
            motor_asyncio = importlib.import_module("motor.motor_asyncio")
            client = motor_asyncio.AsyncIOMotorClient(
                str(target_url),
                serverSelectionTimeoutMS=int(config.timeout_seconds * 1000),
            )
            await client.admin.command("ping")
        except Exception as exc:
            return self._failure(config, account, started_at, str(exc))
        finally:
            if client is not None:
                client.close()

        self._log_success(config, account, started_at)
        return ProviderResult.ok(
            message="MongoDB 连通性正常",
            data=self._target_data(config, account, started_at),
        )

    async def _check_multiple_targets(
        self,
        config: ProbeConfig,
        checker: Callable[[ProbeConfig, ProbeAccount], Awaitable[ProviderResult]],
        success_message: str,
        failure_message: str,
    ) -> ProviderResult:
        """顺序检测多个目标并汇总结果。"""
        results: list[ProviderResult] = []
        for account in config.accounts:
            # 保留每个目标的独立结果, 方便定位失败地址。
            result = await checker(config, account)
            results.append(result)

        target_results = [
            {
                "success": result.success,
                "message": result.message,
                **result.data,
            }
            for result in results
        ]
        data = {"kind": config.kind, "targets": target_results}
        if all(result.success for result in results):
            return ProviderResult.ok(message=success_message, data=data)
        return ProviderResult.fail(message=failure_message, data=data)

    def _failure(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
        started_at: float,
        error: str,
    ) -> ProviderResult:
        """构造连通性失败结果。"""
        data = self._target_data(config, account, started_at)
        data["error"] = error
        self.log(
            f"[{account.name}] {config.kind.upper()} 连通性异常: {error}, "
            f"耗时 {data['elapsed_ms']}ms"
        )
        return ProviderResult.fail(
            message=f"{config.kind.upper()} 连通性异常",
            data=data,
        )

    def _log_success(
        self,
        config: ProbeConfig,
        account: ProbeAccount,
        started_at: float,
    ) -> None:
        """记录连通性成功日志。"""
        elapsed_ms = self._elapsed_ms(started_at)
        target_url = account.url
        target = f"{config._target_host(target_url)}:{config._target_port(target_url)}"
        self.log(
            f"[{account.name}] {config.kind} 连通性正常, "
            f"目标 {target}, 耗时 {elapsed_ms}ms"
        )

    @staticmethod
    def _mysql_connection_url(target_url: AnyUrl) -> str:
        """返回保留完整 URL 信息的 MySQL 异步连接地址。"""
        parsed = urlsplit(str(target_url))
        return urlunsplit(
            (
                MYSQL_ASYNC_SCHEME,
                parsed.netloc,
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )

    @staticmethod
    def _create_unverified_ssl_context() -> ssl.SSLContext:
        """创建不校验证书的 SSL 上下文。"""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    @staticmethod
    def _target_data(
        config: ProbeConfig,
        account: ProbeAccount,
        started_at: float,
    ) -> dict[str, Any]:
        """构造目标检测数据。"""
        target_url = account.url
        return {
            "kind": config.kind,
            "account": account.name,
            "url": config._display_url(target_url),
            "host": config._target_host(target_url),
            "port": config._target_port(target_url),
            "elapsed_ms": ProbeProvider._elapsed_ms(started_at),
        }

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        """计算毫秒耗时。"""
        return int((perf_counter() - started_at) * 1000)
