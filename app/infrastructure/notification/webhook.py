"""Generic webhook notification driver posting a JSON payload."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.runtime.driver import DriverTestResult
from app.runtime.notification.models import NotificationMessage, NotificationResult

if TYPE_CHECKING:
    from app.infrastructure.http.client import HttpClient


class WebhookDriver:
    """POSTs the message as JSON to the configured URL."""

    def __init__(self, *, http: HttpClient) -> None:
        """Borrow the application connection pool."""
        self.http = http

    async def send(
        self, message: NotificationMessage, config: dict[str, Any]
    ) -> NotificationResult:
        """POST and accept any 2xx as delivered."""
        url = str(config["url"])
        response = await self.http.post(
            url,
            json={
                "title": message.title,
                "content": message.content,
            },
            timeout=15,
        )
        if 200 <= response.status_code < 300:
            return NotificationResult(True, "webhook")
        return NotificationResult(
            False, "webhook", error=f"Webhook returned {response.status_code}"
        )

    async def test(self, config: dict[str, Any]) -> DriverTestResult:
        """Validate URL shape; a HEAD/GET probe is best-effort."""
        url = str(config.get("url", ""))
        if not url.startswith(("http://", "https://")):
            return DriverTestResult(False, "Webhook URL 必须以 http(s):// 开头")
        try:
            response = await self.http.get(url, timeout=10)
            return DriverTestResult(True, f"Webhook 可达 (HTTP {response.status_code})")
        except Exception:
            return DriverTestResult(False, "Webhook 不可达")
