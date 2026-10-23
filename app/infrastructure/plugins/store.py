"""Provider plugin source storage on the local filesystem."""

from __future__ import annotations

import ast
import os
import re
import shutil
import tempfile
from pathlib import Path

from app.core.exceptions import ConflictError, NotFoundError, ValidationError

PROVIDERS_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "providers"
"""Absolute path of the providers package holding the plugin sources."""

RESERVED_DIRECTORIES: frozenset[str] = frozenset({"shared"})
"""Directories that never hold a provider and cannot be written through the API."""

PROVIDER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
"""Allowed provider names, matching the directory name."""

MAIN_FILENAME = "main.py"
"""Entry file expected inside every provider directory."""


class ProviderStore:
    """Reads and writes provider sources with atomic replacement."""

    def __init__(self, root: Path = PROVIDERS_DIRECTORY) -> None:
        """Bind the providers root directory."""
        self.root = root

    def list_directories(self) -> list[str]:
        """Provider directories currently present on disk."""
        if not self.root.exists():
            return []
        return sorted(
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and not child.name.startswith(("_", "."))
        )

    def exists(self, name: str) -> bool:
        """Whether the provider directory exists."""
        return (self.root / name / MAIN_FILENAME).is_file()

    def read(self, name: str) -> str:
        """Source of main.py or 404."""
        path = self._main_path(name)
        if not path.is_file():
            raise NotFoundError(f"Provider '{name}' 源码不存在")
        return path.read_text(encoding="utf-8")

    def write(self, name: str, code: str) -> Path:
        """Write main.py atomically, creating the package directory."""
        self._validate_name(name)
        self._validate_syntax(code)
        directory = self.root / name
        directory.mkdir(parents=True, exist_ok=True)
        init = directory / "__init__.py"
        if not init.exists():
            init.write_text(
                f'"""Provider {name}."""\n', encoding="utf-8"
            )
        target = directory / MAIN_FILENAME
        handle, temp_name = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(code)
            os.replace(temp_name, target)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return target

    def delete(self, name: str) -> None:
        """Remove the provider directory entirely."""
        self._validate_name(name)
        directory = self.root / name
        if not directory.is_dir():
            raise NotFoundError(f"Provider '{name}' 不存在")
        shutil.rmtree(directory)

    def _main_path(self, name: str) -> Path:
        """Resolve main.py under the providers root, refusing path escapes."""
        self._validate_name(name)
        return self.root / name / MAIN_FILENAME

    def _validate_name(self, name: str) -> None:
        """Reject reserved and malformed provider names."""
        if name in RESERVED_DIRECTORIES:
            raise ConflictError(f"'{name}' 是保留目录, 不能作为 Provider 名称")
        if not PROVIDER_NAME_PATTERN.fullmatch(name):
            raise ValidationError(
                "Provider 名称必须匹配 ^[a-z][a-z0-9_]{2,63}$ (小写字母开头, 允许数字和下划线)"
            )

    def _validate_syntax(self, code: str) -> None:
        """Reject code that does not parse, before touching the filesystem."""
        try:
            ast.parse(code)
        except SyntaxError as error:
            location = f"第 {error.lineno} 行" if error.lineno else "未知位置"
            raise ValidationError(f"代码语法错误 ({location}): {error.msg}") from error
