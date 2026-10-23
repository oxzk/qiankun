"""Install and inspect Python packages in the running application environment."""

from __future__ import annotations

import asyncio
import importlib.metadata
import re
from dataclasses import dataclass
from typing import Any

PROTECTED_PACKAGES: frozenset[str] = frozenset(
    {
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic-settings",
        "sqlalchemy",
        "asyncpg",
        "alembic",
        "loguru",
        "croniter",
        "pyjwt",
        "argon2-cffi",
        "playwright",
        "curl-cffi",
    }
)
"""Packages the dependency API refuses to change."""

INSTALL_TIMEOUT_SECONDS = 300
"""Hard timeout for one uv install or uninstall call."""

_SPEC_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(\[[A-Za-z0-9._,-]+\])?([<>=!~]=?[^;]+)?$")
"""Conservative PEP 508 subset accepted from the API."""


class DependencyError(Exception):
    """Installation failed; the message carries uv output."""


@dataclass(frozen=True)
class InstalledPackage:
    """One distribution visible to the running interpreter."""

    name: str
    version: str


def normalize(name: str) -> str:
    """Canonical distribution name for comparisons."""
    return re.sub(r"[-_.]+", "-", name).lower()


def package_name(spec: str) -> str:
    """Distribution name of a requirement spec."""
    return normalize(re.split(r"[<>=!~\[;]", spec, maxsplit=1)[0].strip())


def validate_specs(specs: list[str]) -> list[str]:
    """Reject malformed specs and any attempt to modify a protected package."""
    problems: list[str] = []
    for spec in specs:
        cleaned = spec.strip()
        if not cleaned:
            problems.append("依赖项不能为空")
            continue
        if not _SPEC_PATTERN.fullmatch(cleaned):
            problems.append(f"非法的依赖格式: {cleaned}")
            continue
        if package_name(cleaned) in {normalize(p) for p in PROTECTED_PACKAGES}:
            problems.append(f"{cleaned} 属于核心依赖, 不允许通过接口修改")
    return problems


def installed_packages() -> dict[str, str]:
    """All installed distributions keyed by normalized name."""
    result: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            result[normalize(name)] = distribution.version
    return result


def base_requirements() -> dict[str, str]:
    """Versions pinned by the application itself (pyproject dependencies)."""
    try:
        requires = importlib.metadata.requires("qiankun") or []
    except importlib.metadata.PackageNotFoundError:
        return {}
    pinned: dict[str, str] = {}
    for line in requires:
        if "extra ==" in line:
            continue
        name = package_name(line)
        if name:
            pinned[name] = ""
    return pinned


async def _run(command: list[str]) -> tuple[int, str]:
    """Run uv and return its exit code with combined output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=INSTALL_TIMEOUT_SECONDS
        )
    except TimeoutError as error:
        process.kill()
        await process.wait()
        raise DependencyError(
            f"安装超时 (>{INSTALL_TIMEOUT_SECONDS}s): {' '.join(command)}"
        ) from error
    return process.returncode or 0, stdout.decode("utf-8", "replace")


async def install(specs: list[str]) -> str:
    """Install packages into the running environment, returning uv output."""
    if not specs:
        return ""
    code, output = await _run(["uv", "pip", "install", "--no-cache-dir", *specs])
    if code != 0:
        raise DependencyError(output[-4000:] or f"uv exited with {code}")
    return output


async def uninstall(names: list[str]) -> str:
    """Uninstall packages from the running environment."""
    if not names:
        return ""
    code, output = await _run(["uv", "pip", "uninstall", *names])
    if code != 0:
        raise DependencyError(output[-4000:] or f"uv exited with {code}")
    return output


def drift(declared: list[str], installed: dict[str, str]) -> list[dict[str, str]]:
    """Compare declared requirements with what is actually importable."""
    problems: list[dict[str, str]] = []
    for spec in declared:
        name = package_name(spec)
        if name not in installed:
            problems.append({"package": name, "state": "missing", "detail": spec})
            continue
        specifier = spec[len(re.split(r"[<>=!~\[;]", spec, maxsplit=1)[0]) :].strip()
        if specifier and not _matches(installed[name], specifier):
            problems.append(
                {
                    "package": name,
                    "state": "outdated",
                    "detail": f"已安装 {installed[name]}, 期望 {specifier}",
                }
            )
    return problems


def _matches(version: str, specifier: str) -> bool:
    """Check one installed version against a comparison specifier."""
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    try:
        return SpecifierSet(specifier).contains(version, prereleases=True)
    except InvalidSpecifier:
        return True


def describe(declared: list[str]) -> dict[str, Any]:
    """Full dependency picture for the management endpoint."""
    installed = installed_packages()
    protected = sorted(PROTECTED_PACKAGES)
    return {
        "base": sorted(name for name in base_requirements()),
        "extra": list(declared),
        "installed": dict(sorted(installed.items())),
        "drift": drift(declared, installed),
        "protected": protected,
    }
