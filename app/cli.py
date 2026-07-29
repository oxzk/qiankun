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
            default="{}",
            help="Provider 配置 JSON 对象, 默认: {}",
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
            await self.run_provider(args.provider_name, self.parse_config(args.config))

    async def sync_builtin_providers(self) -> None:
        """同步内置 Provider 到数据库。"""
        await db.connect()
        try:
            await self.services.provider_services.sync.sync_builtin_providers()
        finally:
            await db.close()

    async def run_provider(self, provider_name: str, config: dict[str, object]) -> None:
        """优先运行内置 Provider, 不存在时查询数据库 Provider。"""
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
