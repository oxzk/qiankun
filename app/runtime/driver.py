"""Driver test result shared by browser and notification drivers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriverTestResult:
    """Outcome of validating one driver configuration."""

    success: bool
    message: str = ""
