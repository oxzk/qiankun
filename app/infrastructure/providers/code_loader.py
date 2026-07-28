"""Provider 代码加载服务。"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import inspect
import re
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any

from app.config.settings import settings
from app.provider_plugins.base import (
    BaseBrowserProvider,
    BaseCamoufox,
    BaseProvider,
    find_single_provider_class,
)
from app.provider_plugins.contracts import (
    BrowserProviderConfig,
    ProviderConfig,
    ProviderContext,
    ProviderResult,
)
from app.shared.errors import AppError
from app.shared.logger import logger

# 动态 Provider 允许导入的顶级模块白名单（覆盖内置 Provider 依赖）。
ALLOWED_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "abc",
        "asyncio",
        "base64",
        "bs4",
        "camoufox",
        "collections",
        "contextlib",
        "curl_cffi",
        "dataclasses",
        "datetime",
        "email",
        "enum",
        "hashlib",
        "html",
        "http",
        "importlib",
        "inspect",
        "json",
        "logging",
        "math",
        "pathlib",
        "playwright",
        "pydantic",
        "pyrogram",
        "random",
        "re",
        "redis",
        "shutil",
        "sqlalchemy",
        "ssl",
        "string",
        "textwrap",
        "time",
        "types",
        "typing",
        "urllib",
        "uuid",
        "xml",
        "zoneinfo",
    }
)
"""沙箱允许的导入根模块。"""

ALLOWED_APP_PREFIXES = (
    "app.provider_plugins",
    "app.infrastructure",
    "app.shared",
)
"""允许导入的应用内模块前缀。"""

BANNED_CALL_NAMES = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
    }
)
"""禁止的内置调用名。"""

BANNED_ATTRIBUTE_CALLS = frozenset(
    {
        ("os", "system"),
        ("os", "popen"),
        ("os", "exec"),
        ("os", "execl"),
        ("os", "execle"),
        ("os", "execlp"),
        ("os", "execv"),
        ("os", "execve"),
        ("os", "execvp"),
        ("os", "execvpe"),
        ("os", "remove"),
        ("os", "unlink"),
        ("os", "rmdir"),
        ("os", "removedirs"),
        ("os", "rename"),
        ("subprocess", "run"),
        ("subprocess", "Popen"),
        ("subprocess", "call"),
        ("subprocess", "check_output"),
        ("subprocess", "check_call"),
        ("builtins", "eval"),
        ("builtins", "exec"),
        ("builtins", "open"),
    }
)
"""禁止的属性调用。"""


class ProviderCodeLoader:
    """数据库代码 Provider 加载器。"""

    CODE_MODULE_PREFIX = "app.dynamic_providers"
    """数据库代码 Provider 动态模块前缀。"""

    CODE_TEMP_DIR = Path(tempfile.gettempdir()) / "qiankun" / "providers"
    """数据库代码 Provider 临时文件目录。"""

    def __init__(self, sandbox_enabled: bool | None = None) -> None:
        """初始化 Provider 类缓存。"""
        self._class_cache: dict[str, type[BaseProvider]] = {}
        self._sandbox_enabled = (
            settings.provider_code_sandbox if sandbox_enabled is None else sandbox_enabled
        )

    def load_provider_class_from_code(
        self,
        provider_name: str,
        code: str,
        *,
        actor: str | None = None,
        source: str = "runtime",
    ) -> type[BaseProvider]:
        """从数据库代码临时文件加载唯一 Provider 类，相同代码复用缓存。"""
        cache_key = self.code_identity(provider_name, code)
        cached = self._class_cache.get(cache_key)
        if cached is not None:
            return cached

        self.validate_provider_code(provider_name, code)
        code_file = self.write_provider_code_file(provider_name, code)
        module_name = f"{self.CODE_MODULE_PREFIX}.{cache_key}"
        self.ensure_runtime_package(code_file.parent)
        spec = importlib.util.spec_from_file_location(module_name, code_file)
        if spec is None or spec.loader is None:
            raise AppError("Provider 代码临时文件不可加载")
        module = importlib.util.module_from_spec(spec)
        module.__dict__.update(self.code_globals(module_name))
        sys.modules.pop(module_name, None)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            logger.warning(
                "Provider 代码加载失败: name=%s source=%s actor=%s error=%s",
                provider_name,
                source,
                actor or "-",
                exc,
            )
            raise AppError(f"Provider 代码加载失败: {exc}") from exc

        provider_class = find_single_provider_class(module, module_name, label="Provider 代码")
        self._class_cache[cache_key] = provider_class
        logger.info(
            "Provider 代码已加载: name=%s hash=%s source=%s actor=%s sandbox=%s",
            provider_name,
            cache_key,
            source,
            actor or "-",
            self._sandbox_enabled,
        )
        return provider_class

    def validate_provider_code(self, provider_name: str, code: str) -> None:
        """静态校验 Provider 代码安全性。"""
        if not code or not code.strip():
            raise AppError("Provider 代码不能为空")
        try:
            tree = ast.parse(code, filename=provider_name)
        except SyntaxError as exc:
            raise AppError(f"Provider 代码语法错误: {exc.msg}") from exc

        if not self._sandbox_enabled:
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._validate_import_node(node)
            elif isinstance(node, ast.Call):
                self._validate_call_node(node)

    def _validate_import_node(self, node: ast.Import | ast.ImportFrom) -> None:
        """校验导入是否在白名单内。"""
        if isinstance(node, ast.Import):
            module_names = [alias.name for alias in node.names]
        else:
            if node.level and not node.module:
                raise AppError("Provider 代码禁止相对导入")
            module_names = [node.module] if node.module else []
        for module_name in module_names:
            if not module_name:
                continue
            if self._is_allowed_module(module_name):
                continue
            raise AppError(f"Provider 代码禁止导入模块: {module_name}")

    def _is_allowed_module(self, module_name: str) -> bool:
        """判断模块是否允许导入。"""
        root = module_name.split(".", 1)[0]
        if root in ALLOWED_IMPORT_ROOTS:
            return True
        return any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in ALLOWED_APP_PREFIXES)

    def _validate_call_node(self, node: ast.Call) -> None:
        """校验危险函数调用。"""
        func = node.func
        if isinstance(func, ast.Name) and func.id in BANNED_CALL_NAMES:
            raise AppError(f"Provider 代码禁止调用: {func.id}")
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            pair = (func.value.id, func.attr)
            if pair in BANNED_ATTRIBUTE_CALLS:
                raise AppError(f"Provider 代码禁止调用: {func.value.id}.{func.attr}")

    def write_provider_code_file(self, provider_name: str, code: str) -> Path:
        """将 Provider 代码写入临时文件。"""
        self.CODE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        code_file = self.provider_code_path(provider_name, code)
        code_file.write_text(code, encoding="utf-8")
        return code_file

    def provider_code_path(self, provider_name: str, code: str = "") -> Path:
        """返回 Provider 代码临时文件路径。"""
        return self.CODE_TEMP_DIR / f"{self.code_identity(provider_name, code)}.py"

    def code_identity(self, provider_name: str, code: str) -> str:
        """构造 Provider 代码唯一标识。"""
        code_hash = sha256(code.encode("utf-8")).hexdigest()[:12]
        return f"{self.safe_module_name(provider_name)}_{code_hash}"

    @staticmethod
    def safe_module_name(provider_name: str) -> str:
        """将 Provider 名称转换为安全模块名。"""
        safe_name = re.sub(r"[^0-9A-Za-z_]", "_", provider_name.strip())
        if not safe_name:
            safe_name = "provider"
        if safe_name[0].isdigit():
            safe_name = f"provider_{safe_name}"
        return safe_name

    def ensure_runtime_package(self, directory: Path) -> None:
        """确保动态 Provider 运行包存在。"""
        package = sys.modules.get(self.CODE_MODULE_PREFIX)
        if package is None:
            package = ModuleType(self.CODE_MODULE_PREFIX)
            package.__path__ = [str(directory)]  # type: ignore[attr-defined]
            sys.modules[self.CODE_MODULE_PREFIX] = package
            return
        package.__path__ = [str(directory)]  # type: ignore[attr-defined]

    def code_globals(self, module_name: str) -> dict[str, Any]:
        """构建数据库代码 Provider 执行全局变量。"""
        return {
            "__builtins__": self._build_builtins(),
            "__name__": module_name,
            "__package__": self.CODE_MODULE_PREFIX,
            "BaseProvider": BaseProvider,
            "BaseBrowserProvider": BaseBrowserProvider,
            "BaseCamoufox": BaseCamoufox,
            "BrowserProviderConfig": BrowserProviderConfig,
            "ProviderConfig": ProviderConfig,
            "ProviderContext": ProviderContext,
            "ProviderResult": ProviderResult,
        }

    def _build_builtins(self) -> dict[str, Any]:
        """构建受限或不受限内置函数表。"""
        if not self._sandbox_enabled:
            return builtins.__dict__

        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if name not in BANNED_CALL_NAMES and not name.startswith("_")
        }
        safe_builtins["__build_class__"] = builtins.__build_class__
        safe_builtins["__name__"] = "builtins"
        safe_builtins["__import__"] = self._safe_import
        return safe_builtins

    def _safe_import(
        self,
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """白名单限制下的 import 实现。"""
        if level != 0:
            raise ImportError("Provider 代码禁止相对导入")
        if not self._is_allowed_module(name):
            raise ImportError(f"Provider 代码禁止导入模块: {name}")
        return builtins.__import__(name, globals, locals, fromlist, level)

    def invalidate_cache(self, provider_name: str | None = None) -> None:
        """清理 Provider 类缓存。"""
        if provider_name is None:
            self._class_cache.clear()
            return
        prefix = f"{self.safe_module_name(provider_name)}_"
        for key in list(self._class_cache):
            if key.startswith(prefix):
                self._class_cache.pop(key, None)

    @staticmethod
    def source_code_for_provider_class(provider_class: object) -> str:
        """读取内置 Provider 类所在模块源码。"""
        module = inspect.getmodule(provider_class)
        module_file = getattr(module, "__file__", None)
        if not module_file:
            raise AppError("Provider 源码文件不存在")
        return Path(module_file).read_text(encoding="utf-8")
