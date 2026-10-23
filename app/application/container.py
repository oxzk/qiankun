"""Composition root: create, wire and tear down every component."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.services.auth import AuthService
from app.application.services.dependency import DependencyService
from app.application.services.execution import ExecutionService
from app.application.services.provider import ProviderService
from app.infrastructure.plugins.store import ProviderStore
from app.application.services.scheduler.attempt import AttemptExecutor
from app.application.services.scheduler.finalizer import TaskRunFinalizer
from app.application.services.scheduler.policy import SchedulePolicy
from app.application.services.scheduler.runner import TaskRunner
from app.application.services.scheduler.scheduler import TaskScheduler
from app.application.services.stats import StatsService
from app.application.services.system_setting import SystemSettingService
from app.application.services.task import TaskService
from app.core.config import Settings
from app.infrastructure.auth.jwt import JWTManager
from app.infrastructure.auth.password import hash_password
from app.infrastructure.database.engine import Database
from app.infrastructure.database.session import build_session_factory
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.infrastructure.http.client import HttpClient
from app.infrastructure.logging import loguru as loguru_logging
from app.infrastructure.notification.telegram import TelegramDriver
from app.infrastructure.notification.webhook import WebhookDriver
from app.runtime.browser.base import BrowserResolver, BrowserRuntime
from app.runtime.event import EventBus
from app.runtime.execution.log_stream import ExecutionLogStream
from app.runtime.logger import Logger
from app.runtime.notification.base import NotificationDriver, NotificationRuntime
from app.runtime.provider.registry import ProviderRegistry


class _InfraLogger:
    """Adapter funneling runtime messages into loguru."""

    def info(self, message: str, **context: Any) -> None:
        """Info passthrough."""
        from loguru import logger

        logger.info(message)

    def warning(self, message: str, **context: Any) -> None:
        """Warning passthrough."""
        from loguru import logger

        logger.warning(message)

    def error(self, message: str, **context: Any) -> None:
        """Error passthrough."""
        from loguru import logger

        logger.error(message)


class _StreamHandler:
    """Publishes terminal frames into the log stream."""

    def __init__(self, stream: ExecutionLogStream) -> None:
        """Bind the shared stream."""
        self.stream = stream

    async def handle_event(self, event: Any) -> None:
        """Map execution events to stream terminal frames."""
        if not event.execution_id:
            return
        status = event.type.removeprefix("execution.")
        if status in {"completed", "failed", "timeout", "cancelled"}:
            self.stream.handle_terminal(event.execution_id, status)


class _CDPDriverFactory:
    """Builds CDP drivers with configuration read at open() time."""

    def __init__(self, cache: dict[tuple[str, str], dict[str, Any]]) -> None:
        """Share the container's settings cache."""
        self._cache = cache

    def config(self, name: str) -> dict[str, Any]:
        """Return the last known browser config; refreshed per open."""
        return self._cache.get(("browser", name), {})

    def create(self) -> Any:
        """Instantiate the CDP driver with the cached config."""
        from app.infrastructure.browser.cdp import CDPDriver

        return CDPDriver(self.config("cdp"))


@dataclass
class ApplicationContainer:
    """Holds every assembled component for the API layer to consume."""

    settings: Settings
    database: Database
    uow_factory: Any
    providers: ProviderRegistry
    system_settings: SystemSettingService
    stream: ExecutionLogStream
    events: EventBus
    jwt: JWTManager
    http: HttpClient
    tasks: TaskService = field(init=False)
    executions: ExecutionService = field(init=False)
    providers_service: ProviderService = field(init=False)
    dependencies: DependencyService = field(init=False)
    auth: AuthService = field(init=False)
    stats: StatsService = field(init=False)
    scheduler: TaskScheduler = field(init=False)
    browser: BrowserRuntime = field(init=False)
    notifications: NotificationRuntime = field(init=False)
    _initialized: list[Any] = field(default_factory=list)
    _setting_cache: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    @classmethod
    async def create(cls, settings: Settings) -> ApplicationContainer:
        """Initialize in dependency order, rolling back on failure."""
        container = cls(
            settings=settings,
            database=Database(settings.database),
            uow_factory=None,
            providers=ProviderRegistry(),
            system_settings=SystemSettingService(None),
            stream=ExecutionLogStream(),
            events=EventBus(),
            jwt=JWTManager(settings.jwt),
            http=HttpClient(),
        )
        try:
            await container._initialize()
        except Exception:
            await container.shutdown()
            raise
        return container

    async def _initialize(self) -> None:
        """Ordered initialization with reverse-order rollback bookkeeping."""
        loguru_logging.configure(self.settings.logging)
        self._initialized.append(self.database)
        await self.database.initialize()

        session_factory = build_session_factory(self.database.engine)
        self.uow_factory = lambda: UnitOfWork(session_factory)
        self.system_settings.uow_factory = self.uow_factory

        await self.system_settings.bootstrap(hash_password("admin"))

        self.providers.load()

        # Refresh the browser settings cache once at startup; drivers re-read
        # the cache on every open so system_settings updates apply live.
        browser_row = await self._read_setting("browser", "cdp")
        self._setting_cache[("browser", "cdp")] = dict(browser_row.get("value") or {})
        cdp_factory = _CDPDriverFactory(self._setting_cache)
        resolver = BrowserResolver({"cdp": cdp_factory.create}, cdp_factory.config)
        self.browser = BrowserRuntime(resolver)

        drivers: dict[str, NotificationDriver] = {
            "telegram": TelegramDriver(http=self.http),  # type: ignore[dict-item]
            "webhook": WebhookDriver(http=self.http),  # type: ignore[dict-item]
        }
        self.notifications = NotificationRuntime(drivers, _InfraLogger())

        # Scheduler stack.
        executor = AttemptExecutor(
            self.settings.runtime.default_timeout,
            self.settings.runtime.cleanup_timeout,
            self.stream,
        )
        executor.attach_browser_runtime(self.browser)
        runner = TaskRunner(self.uow_factory, self.providers, executor)
        policy = SchedulePolicy()
        self.scheduler = TaskScheduler(self.uow_factory, policy, runner, self.settings.scheduler)

        # Services.
        self.tasks = TaskService(self.uow_factory, self.providers, self.scheduler)
        self.executions = ExecutionService(self.uow_factory, self.stream, self.scheduler)
        self.provider_store = ProviderStore()
        self.providers_service = ProviderService(
            self.providers, self.stream, self.provider_store, self.uow_factory
        )
        self.dependencies = DependencyService(self.uow_factory, self.providers)
        self.auth = AuthService(self.uow_factory, self.jwt)
        self.stats = StatsService(self.uow_factory)

        # Event wiring: SSE terminal frames and notification dispatch.
        finalizer = TaskRunFinalizer(self.uow_factory, self.notifications, _InfraLogger())
        self.events.subscribe(_StreamHandler(self.stream))
        self.events.subscribe(finalizer)

        # Settings writes refresh the browser cache so CDP picks them up live.
        self.system_settings.on_update = self._on_setting_updated

        # Restore plugin dependencies, then rescan providers so a fresh
        # container serves every plugin immediately.
        await self._restore_dependencies()
        self.providers.load()

        await self.scheduler.start()

    async def _restore_dependencies(self) -> None:
        """Install missing manifest packages; a failure never blocks startup."""
        try:
            await self.dependencies.sync()
        except Exception as error:
            from loguru import logger

            logger.warning(f"依赖恢复失败, 服务继续启动: {error}")

    async def _read_setting(self, scope: str, key: str) -> dict[str, Any]:
        """Read one setting row tolerating a missing table during first boot."""
        try:
            return await self.system_settings.get(scope, key)
        except Exception:
            return {}

    async def _on_setting_updated(self, scope: str, key: str) -> None:
        """Invalidate the cached browser config when browser/cdp changes."""
        if (scope, key) == ("browser", "cdp"):
            row = await self._read_setting(scope, key)
            self._setting_cache[(scope, key)] = dict(row.get("value") or {})

    async def shutdown(self) -> None:
        """Tear down in reverse initialization order."""
        try:
            await self.scheduler.stop()
        except Exception:
            pass
        await self.http.close()
        await self.database.shutdown()

    def setting(self, scope: str, key: str) -> dict[str, Any]:
        """Synchronous settings accessor used by drivers at call time."""
        return self._setting_cache.get((scope, key), {})


def _logger_protocol_check(_: Logger) -> None:  # pragma: no cover
    """Compile-time anchor proving _InfraLogger satisfies the Logger protocol."""
