"""Telegram Bot API notification driver, credentials passed per call."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.runtime.driver import DriverTestResult
from app.runtime.notification.models import NotificationMessage, NotificationResult

if TYPE_CHECKING:
    from app.infrastructure.http.client import HttpClient


class TelegramDriver:
    """Delivers plain text via the Bot API using the shared HTTP client."""

    def __init__(self, *, http: HttpClient) -> None:
        """Borrow the application connection pool."""
        self.http = http

    async def send(
        self, message: NotificationMessage, config: dict[str, Any]
    ) -> NotificationResult:
        """Check both HTTP status and the Telegram ok field."""
        endpoint = str(config.get("endpoint", "https://api.telegram.org")).rstrip("/")
        text = f"{message.title}\n{message.content}"
        response = await self.http.post(
            f"{endpoint}/bot{config['bot_token']}/sendMessage",
            json={"chat_id": config["chat_id"], "text": text[:4096]},
            timeout=15,
        )
        if response.status_code != 200:
            return NotificationResult(False, "telegram", error="Telegram rejected the message")
        data = response.json()
        if data.get("ok") is not True:
            return NotificationResult(False, "telegram", error="Telegram rejected the message")
        return NotificationResult(True, "telegram", message_id=str(data["result"]["message_id"]))

    async def test(self, config: dict[str, Any]) -> DriverTestResult:
        """Validate bot credentials and target chat without sending content."""
        try:
            endpoint = str(config.get("endpoint", "https://api.telegram.org")).rstrip("/")
            for method, params in (("getMe", {}), ("getChat", {"chat_id": config["chat_id"]})):
                response = await self.http.get(
                    f"{endpoint}/bot{config['bot_token']}/{method}", params=params
                )
                if response.status_code != 200 or response.json().get("ok") is not True:
                    return DriverTestResult(False, "Telegram 认证或目标会话检查失败")
            return DriverTestResult(True, "Telegram 配置检查成功")
        except Exception:
            return DriverTestResult(False, "Telegram 连接或配置失败")
