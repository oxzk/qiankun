"""Probe provider: multi-target connectivity checks with per-target live logs."""

from __future__ import annotations

import importlib
import ssl
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, ClassVar
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from curl_cffi import requests
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.providers.probe.config import ProbeAccount, ProbeConfig
from app.runtime.provider.base import BaseProvider
from app.runtime.provider.models import ProviderConfig, ProviderContext, ProviderResult

REDIS_CHECK_VALUE = "1"
"""Value written and removed for Redis checks."""

HTTP_METHOD = "GET"
"""HTTP check request method."""

HTTP_EXPECTED_STATUS_MIN = 200
HTTP_EXPECTED_STATUS_MAX = 399
"""HTTP status range accepted as reachable."""

MYSQL_ASYNC_SCHEME = "mysql+aiomysql"
"""SQLAlchemy async scheme for MySQL checks."""

_TargetChecker = Callable[[ProviderContext, ProbeConfig, ProbeAccount], Awaitable[ProviderResult]]
"""Per-account check callable shared by every kind."""


class ProbeProvider(BaseProvider):
    """Runs one connectivity check kind across every configured account."""

    name: ClassVar[str] = "probe"
    config_schema: ClassVar[type[ProviderConfig]] = ProbeConfig  # type: ignore[assignment]
    capabilities: ClassVar[frozenset[str]] = frozenset()

    async def execute(self, ctx: ProviderContext, config: ProviderConfig) -> ProviderResult:
        """Dispatch by configured kind and aggregate per-target results."""
        if not isinstance(config, ProbeConfig):
            raise TypeError("Probe 配置类型无效")
        started = perf_counter()
        ctx.logger.info(
            f"开始 {config.kind} 连通性检测, 共 {len(config.accounts)} 个目标",
            kind=config.kind,
            targets=len(config.accounts),
        )
        checkers: dict[str, tuple[_TargetChecker, str]] = {
            "HTTP": (self._check_http, "HTTP 连通性正常"),
            "Redis": (self._check_redis, "Redis 连通性正常"),
            "MySQL": (self._check_mysql, "MySQL 连通性正常"),
            "PostgreSQL": (self._check_postgresql, "PostgreSQL 连通性正常"),
            "RabbitMQ": (self._check_rabbitmq, "RabbitMQ 连通性正常"),
            "MongoDB": (self._check_mongodb, "MongoDB 连通性正常"),
        }
        checker, success_message = checkers[config.kind]
        result = await self._run_targets(ctx, config, checker, success_message)
        ctx.logger.info(
            f"{config.kind} 连通性检测完成, {result.message}, 总耗时 {_elapsed_ms(started)}ms",
            kind=config.kind,
            elapsed_ms=_elapsed_ms(started),
        )
        return result

    async def _run_targets(
        self,
        ctx: ProviderContext,
        config: ProbeConfig,
        checker: _TargetChecker,
        success_message: str,
    ) -> ProviderResult:
        """Check every account sequentially, keeping one result per target."""
        results: list[ProviderResult] = []
        for account in config.accounts:
            ctx.logger.info(
                f"[{account.name}] 开始检测 {config._display_url(account.url)}",
                account=account.name,
                kind=config.kind,
                url=config._display_url(account.url),
            )
            results.append(await checker(ctx, config, account))

        target_results = [
            {"success": result.success, "message": result.message, **result.data}
            for result in results
        ]
        data = {"kind": config.kind, "targets": target_results}
        if all(result.success for result in results):
            return ProviderResult.ok(success_message, data)
        return ProviderResult.fail(f"{config.kind} 连通性存在异常目标", data)

    async def _check_http(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one HTTP target: GET and expect a 2xx/3xx status."""
        started = perf_counter()
        try:
            async with requests.AsyncSession(impersonate="chrome") as session:
                response = await session.request(
                    HTTP_METHOD,
                    str(account.url),
                    timeout=config.timeout_seconds,
                )
        except requests.RequestsError as exc:
            return self._failure(ctx, config, account, started, str(exc))

        elapsed_ms = _elapsed_ms(started)
        success = HTTP_EXPECTED_STATUS_MIN <= response.status_code <= HTTP_EXPECTED_STATUS_MAX
        data = {
            "kind": config.kind,
            "account": account.name,
            "url": config._display_url(account.url),
            "method": HTTP_METHOD,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        }
        if success:
            ctx.logger.info(
                f"[{account.name}] HTTP 连通性正常, 状态码 {response.status_code}, "
                f"耗时 {elapsed_ms}ms",
                account=account.name,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )
            return ProviderResult.ok("HTTP 连通性正常", data)
        ctx.logger.warning(
            f"[{account.name}] HTTP 响应状态码不符合预期, "
            f"期望 {HTTP_EXPECTED_STATUS_MIN}-{HTTP_EXPECTED_STATUS_MAX}, "
            f"实际 {response.status_code}, 耗时 {elapsed_ms}ms",
            account=account.name,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return ProviderResult.fail("HTTP 响应状态码不符合预期", data)

    async def _check_redis(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one Redis target by writing and deleting a random key."""
        started = perf_counter()
        client: Any | None = None
        set_response: Any = None
        try:
            redis_asyncio: Any = importlib.import_module("redis.asyncio")
            client = redis_asyncio.from_url(
                str(account.url),
                socket_connect_timeout=config.timeout_seconds,
                socket_timeout=config.timeout_seconds,
                decode_responses=True,
            )
            check_key = f"qiankun:probe:{uuid4().hex}"
            set_response = await client.set(check_key, REDIS_CHECK_VALUE)
            await client.delete(check_key)
        except Exception as exc:
            return self._failure(ctx, config, account, started, str(exc))
        finally:
            if client is not None:
                await client.aclose()

        data = self._target_data(config, account, started)
        if set_response is True or set_response == "OK":
            return self._succeed(ctx, config, account, data)
        ctx.logger.warning(
            f"[{account.name}] Redis SET 响应不符合预期, 期望 True 或 OK, "
            f"实际 {set_response!r}, 耗时 {data['elapsed_ms']}ms",
            account=account.name,
            elapsed_ms=data["elapsed_ms"],
        )
        return ProviderResult.fail("Redis SET 响应不符合预期", data)

    async def _check_mysql(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one MySQL target by running SELECT 1."""
        started = perf_counter()
        engine: Any | None = None
        try:
            engine = create_async_engine(
                self._mysql_connection_url(account.url),
                connect_args={
                    "connect_timeout": config.timeout_seconds,
                    "ssl": self._create_unverified_ssl_context(),
                },
            )
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            return self._failure(ctx, config, account, started, str(exc))
        finally:
            if engine is not None:
                await engine.dispose()

        return self._succeed(ctx, config, account, self._target_data(config, account, started))

    async def _check_postgresql(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one PostgreSQL target by running SELECT 1."""
        started = perf_counter()
        connection: Any | None = None
        try:
            connection = await asyncpg.connect(
                str(account.url),
                timeout=config.timeout_seconds,
                ssl=self._create_unverified_ssl_context(),
            )
            await connection.fetchval("SELECT 1")
        except Exception as exc:
            return self._failure(ctx, config, account, started, str(exc))
        finally:
            if connection is not None:
                await connection.close()

        return self._succeed(ctx, config, account, self._target_data(config, account, started))

    async def _check_rabbitmq(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one RabbitMQ target by publishing and consuming one message."""
        started = perf_counter()
        connection: Any | None = None
        channel: Any | None = None
        try:
            aio_pika: Any = importlib.import_module("aio_pika")
            connection = await aio_pika.connect_robust(
                str(account.url),
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
            incoming = await queue.get(timeout=config.timeout_seconds)
            if incoming is None:
                raise RuntimeError("RabbitMQ 未消费到检测消息")
            consumed_body = incoming.body
            await incoming.ack()
            if consumed_body != message_body:
                raise RuntimeError("RabbitMQ 消费消息与生产消息不一致")
        except Exception as exc:
            return self._failure(ctx, config, account, started, str(exc))
        finally:
            try:
                if channel is not None:
                    await channel.close()
            finally:
                if connection is not None:
                    await connection.close()

        return self._succeed(ctx, config, account, self._target_data(config, account, started))

    async def _check_mongodb(
        self, ctx: ProviderContext, config: ProbeConfig, account: ProbeAccount
    ) -> ProviderResult:
        """Check one MongoDB target with the ping command."""
        started = perf_counter()
        client: Any | None = None
        try:
            motor_asyncio: Any = importlib.import_module("motor.motor_asyncio")
            client = motor_asyncio.AsyncIOMotorClient(
                str(account.url),
                serverSelectionTimeoutMS=int(config.timeout_seconds * 1000),
            )
            await client.admin.command("ping")
        except Exception as exc:
            return self._failure(ctx, config, account, started, str(exc))
        finally:
            if client is not None:
                client.close()

        return self._succeed(ctx, config, account, self._target_data(config, account, started))

    def _succeed(
        self,
        ctx: ProviderContext,
        config: ProbeConfig,
        account: ProbeAccount,
        data: dict[str, Any],
    ) -> ProviderResult:
        """Log one successful target and build its ok result."""
        target = f"{data['host']}:{data['port']}"
        ctx.logger.info(
            f"[{account.name}] {config.kind} 连通性正常, 目标 {target}, "
            f"耗时 {data['elapsed_ms']}ms",
            account=account.name,
            kind=config.kind,
            target=target,
            elapsed_ms=data["elapsed_ms"],
        )
        return ProviderResult.ok(f"{config.kind} 连通性正常", data)

    def _failure(
        self,
        ctx: ProviderContext,
        config: ProbeConfig,
        account: ProbeAccount,
        started: float,
        error: str,
    ) -> ProviderResult:
        """Log one failed target and build its fail result."""
        data = self._target_data(config, account, started)
        data["error"] = error
        ctx.logger.error(
            f"[{account.name}] {config.kind.upper()} 连通性异常: {error}, "
            f"耗时 {data['elapsed_ms']}ms",
            account=account.name,
            kind=config.kind,
            elapsed_ms=data["elapsed_ms"],
        )
        return ProviderResult.fail(f"{config.kind.upper()} 连通性异常", data)

    @staticmethod
    def _target_data(
        config: ProbeConfig, account: ProbeAccount, started: float
    ) -> dict[str, Any]:
        """Build the shared per-target result payload."""
        return {
            "kind": config.kind,
            "account": account.name,
            "url": config._display_url(account.url),
            "host": config._target_host(account.url),
            "port": config._target_port(account.url),
            "elapsed_ms": _elapsed_ms(started),
        }

    @staticmethod
    def _mysql_connection_url(account_url: Any) -> str:
        """Rewrite the mysql:// URL onto the async aiomysql scheme."""
        parsed = urlsplit(str(account_url))
        return urlunsplit(
            (MYSQL_ASYNC_SCHEME, parsed.netloc, parsed.path, parsed.query, parsed.fragment)
        )

    @staticmethod
    def _create_unverified_ssl_context() -> ssl.SSLContext:
        """Probe targets often use self-signed certificates; reachability is the goal."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context


def _elapsed_ms(started: float) -> int:
    """Milliseconds since the given monotonic start."""
    return max(0, int((perf_counter() - started) * 1000))
