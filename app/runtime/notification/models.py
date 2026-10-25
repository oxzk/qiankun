"""Notification message and result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationMessage:
    """Plain text payload delivered to one channel."""

    title: str
    content: str


@dataclass(frozen=True)
class NotificationResult:
    """Outcome of one delivery attempt."""

    success: bool
    channel: str
    message_id: str = ""
    error: str = ""
