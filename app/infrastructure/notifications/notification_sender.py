"""通知发送服务。"""

from __future__ import annotations

from typing import Any

from app.shared.errors import AppError
from app.infrastructure.http.requester import Requester
from app.infrastructure.notifications.target import NotificationTarget
from app.shared.enums import NotifyType
from app.shared.logger import logger


class NotificationSender:
    """通知发送服务。"""

    def __init__(self, requester: Requester) -> None:
        """初始化通知发送服务。"""
        self.requester = requester

    async def send_notification(self, target: NotificationTarget, message: str) -> None:
        """按通知渠道类型发送消息。"""
        if target.notify_type == NotifyType.TELEGRAM:
            await self._send_telegram(target.config, message)
            return
        if target.notify_type == NotifyType.WEBHOOK:
            await self._send_webhook(target.config, message)
            return
        raise AppError(f"不支持的通知类型: {target.notify_type}")

    async def _send_telegram(self, config: dict[str, Any], message: str) -> None:
        """发送 Telegram 通知。"""
        bot_token = str(config.get("bot_token") or "").strip()
        chat_id = str(config.get("chat_id") or "").strip()
        api_base = str(config.get("api_base") or "https://api.telegram.org").rstrip("/")
        if not bot_token or not chat_id:
            raise AppError("Telegram 通知缺少 bot_token 或 chat_id")

        url = f"{api_base}/bot{bot_token}/sendMessage"
        await self.requester.post_json(url, json={"chat_id": chat_id, "text": message})

    async def _send_webhook(self, config: dict[str, Any], message: str) -> None:
        """发送 Webhook 通知。"""
        url = str(config.get("url") or "").strip()
        if not url:
            raise AppError("Webhook 通知缺少 url")
        headers = config.get("headers") if isinstance(config.get("headers"), dict) else {}
        await self.requester.post_json(url, json={"message": message}, headers=headers)

    async def send_safely(self, target: NotificationTarget, message: str) -> None:
        """发送通知并吞掉异常以避免影响任务状态。"""
        try:
            await self.send_notification(target, message)
        except Exception as exc:
            logger.exception("通知发送失败: %s", exc)
