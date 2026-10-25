"""Redaction of secrets in logs, events, results and responses."""

from __future__ import annotations

import re
from typing import Any, Protocol

_KEY = re.compile(
    r"(pass(word)?|secret|token|api[-_]?key|authorization|cookie|credential)", re.IGNORECASE
)
_VALUE = re.compile(r"(bearer\s+\S+|sk-[A-Za-z0-9_-]{8,})", re.IGNORECASE)
_URL = re.compile(r"(?<=//)[^\s@/:]+:[^\s@/]+@")

REDACTED = "[REDACTED]"


class Logger(Protocol):
    """Logging contract handed to providers."""

    def info(self, message: str, **context: Any) -> None:
        """Informational entry."""
        ...

    def warning(self, message: str, **context: Any) -> None:
        """Warning entry."""
        ...

    def error(self, message: str, **context: Any) -> None:
        """Error entry."""
        ...


def redact(value: Any, secrets: list[str] | None = None) -> Any:
    """Recursively mask credential-like keys, values and URL userinfo."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _KEY.search(str(key)) else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        text = _URL.sub(f"{REDACTED}@", value)
        text = _VALUE.sub(REDACTED, text)
        for secret in secrets or []:
            if secret and secret != REDACTED:
                text = text.replace(secret, REDACTED)
        return text
    return value
