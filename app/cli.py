"""命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import TYPE_CHECKING, Any

from app.infrastructure.database.session import db
from app.infrastructure.providers.builtin_provider_registry import BuiltinProviderRegistry
from app.shared.errors import AppError
from app.shared.logger import logger

if TYPE_CHECKING:
    from app.bootstrap.container import ApplicationContainer


class CliApplication:
    """QianKun 命令行应用。"""

    def __init__(self, services: ApplicationContainer | None = None) -> None:
        """初始化命令行应用依赖。"""
        self._services = services

    @property
    def services(self) -> ApplicationContainer:
        """返回应用服务容器。"""
        if self._services is None:
            from app.bootstrap.container import ApplicationContainer

            self._services = ApplicationContainer()
        return self._services

    def build_parser(self) -> argparse.ArgumentParser:
        """构建命令行参数解析器。"""
        parser = argparse.ArgumentParser(description="QianKun 管理命令")
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="列出可执行的内置 Provider",
        )
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("sync", help="同步内置 Provider 到数据库")
        run_parser = subparsers.add_parser("run", help="运行指定 Provider")
        run_parser.add_argument("provider_name", help="Provider 名称")
        run_parser.add_argument(
            "--config",
            default=None,
            help="Provider 配置 JSON 对象; 指定时直接使用该配置, 不读取数据库",
        )
        run_parser.add_argument(
            "--task",
            default=None,
            help="任务 ID 或任务名称; 未指定 --config 时从该任务读取配置, 默认取 Provider 的第一个任务",
        )
        return parser

    async def run_async(self, argv: list[str] | None = None) -> None:
        """异步执行命令行主流程。"""
        parser = self.build_parser()
        args = parser.parse_args(argv)

        if args.list:
            self.list_builtin_providers()
            return
        if args.command is None:
            parser.error("必须指定命令或使用 -l/--list")
        if args.command == "sync":
            await self.sync_builtin_providers()
            return
        if args.command == "run":
            await self.run_provider(
                args.provider_name,
                args.config,
                args.task,
            )

    async def sync_builtin_providers(self) -> None:
        """同步内置 Provider 到数据库。"""
        await db.connect()
        try:
            await self.services.provider_services.sync.sync_builtin_providers()
        finally:
            await db.close()

    async def run_provider(
        self,
        provider_name: str,
        raw_config: str | None,
        task_selector: str | None,
    ) -> None:
        """运行 Provider。

        指定 ``--config`` 时直接使用该配置, 不读取数据库;
        未指定时从数据库任务配置中读取。
        """
        if raw_config is not None:
            config = self.parse_config(raw_config)
            await self._execute_provider_cls(provider_name, config)
            return

        config = await self._load_task_config(provider_name, task_selector)
        await self._execute_provider_cls(provider_name, config)

    async def _execute_provider_cls(
        self,
        provider_name: str,
        config: dict[str, object],
    ) -> None:
        """执行 Provider, 内置优先, 不存在时使用数据库中的代码。"""
        registry = BuiltinProviderRegistry()
        try:
            provider_class = registry.get(provider_name)
        except AppError as exc:
            if exc.status_code != 404:
                raise
        else:
            await self.services.provider_services.execution.test_run_provider_class(
                provider_class,
                provider_name,
                config,
            )
            return

        await db.connect()
        try:
            await self.services.provider_services.execution.test_run_provider(
                provider_name,
                config,
            )
        finally:
            await db.close()

    async def _load_task_config(
        self,
        provider_name: str,
        task_selector: str | None,
    ) -> dict[str, object]:
        """从数据库任务中读取 Provider 配置。"""
        await db.connect()
        try:
            async with self.services.uow_factory() as uow:
                tasks = await uow.tasks.list_by_provider_name(provider_name)
        finally:
            await db.close()

        if not tasks:
            raise AppError(f"Provider {provider_name} 没有可用的任务配置")
        task = self._select_task(provider_name, tasks, task_selector)
        config = dict(task.provider_config or {})
        logger.info(
            "使用任务配置: provider=%s task_id=%s task_name=%s",
            provider_name,
            task.id,
            task.name,
        )
        return config

    @staticmethod
    def _select_task(
        provider_name: str,
        tasks: list[Any],
        task_selector: str | None,
    ) -> Any:
        """按 ID 或名称选择任务, 未指定时返回第一个任务。"""
        if task_selector is None:
            return tasks[0]

        normalized = task_selector.strip()
        for task in tasks:
            if str(task.id) == normalized:
                return task
        matched_by_name = [task for task in tasks if task.name == normalized]
        if len(matched_by_name) == 1:
            return matched_by_name[0]
        if len(matched_by_name) > 1:
            raise AppError(f"任务名称 {normalized} 重复, 请改用任务 ID")
        raise AppError(f"Provider {provider_name} 下不存在任务: {normalized}")

    def list_builtin_providers(self) -> None:
        """列出可执行的内置 Provider, 不读取数据库。"""
        registry = BuiltinProviderRegistry()
        registry.load_providers()
        providers = sorted(
            registry.list_infos(),
            key=lambda item: str(item["name"]),
        )
        for item in providers:
            print(str(item["name"]))

    @staticmethod
    def parse_config(raw_config: str) -> dict[str, object]:
        """解析 Provider CLI 配置。"""
        try:
            config: Any = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Provider 配置不是合法 JSON: {exc.msg}") from exc
        if not isinstance(config, dict):
            raise ValueError("Provider 配置必须是 JSON 对象")
        return config

    def run(self) -> None:
        """运行命令行应用并记录异常。"""
        try:
            asyncio.run(self.run_async())
        except Exception as exc:
            logger.exception("命令执行失败: %s", exc)
            raise SystemExit(1) from exc


def main() -> None:
    """CLI 入口函数。"""
    CliApplication().run()


if __name__ == "__main__":
    main()
