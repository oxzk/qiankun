"""Loguru setup: console sink, optional file sink, redaction at the boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.api.middleware import REQUEST_ID
from app.core.config import LoggingSettings
from app.runtime.logger import redact

logger.remove()
_CONSOLE_ID: int | None = None
_FILE_ID: int | None = None

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{extra[request_id]} | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


def _patch(record: Any) -> None:
    """Redact the formatted message and bind the current request id."""
    record["extra"]["request_id"] = REQUEST_ID.get() or "-"
    record["message"] = redact(str(record["message"]))


def configure(settings: LoggingSettings) -> None:
    """Replace sinks atomically; keep old ones until new ones succeed."""
    global _CONSOLE_ID, _FILE_ID
    logger.configure(patcher=_patch, extra={"request_id": "-"})
    new_console = logger.add(sys.stderr, level=settings.level, format=_FORMAT)
    new_file = None
    if settings.directory:
        log_dir = Path(settings.directory)
        log_dir.mkdir(parents=True, exist_ok=True)
        new_file = logger.add(
            log_dir / "qiankun.log",
            level=settings.level,
            format=_FORMAT,
            rotation=settings.rotation,
            retention=settings.retention,
            encoding="utf-8",
        )
    for sink in (_CONSOLE_ID, _FILE_ID):
        if sink is not None:
            try:
                logger.remove(sink)
            except ValueError:
                pass
    _CONSOLE_ID = new_console
    _FILE_ID = new_file
