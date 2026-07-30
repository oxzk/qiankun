"""Telegram 消息发送 Provider。"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

from pydantic import Field, ValidationInfo, field_validator
from pyrogram import Client, filters
from redis import asyncio as redis_asyncio

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult

SESSION_KEY_PREFIX = "pyrogram:session:"
"""Pyrogram session 在 Redis 中的 key 前缀。"""

REPLY_TIMEOUT_SECONDS = 30.0
"""读取第一条回复的固定超时时间。"""


class TelegramSendAccount(ProviderConfig):
    """Telegram 单账号发送配置。"""

    name: str = Field(description="账号标识")
    target: int | str = Field(description="目标聊天 ID, 用户名或会话标题")
    message: str = Field(description="待发送消息")

    @field_validator("name", "target", "message")
    @classmethod
    def validate_required_text(cls, value: int | str, info: ValidationInfo) -> int | str:
        """校验必填文本字段。"""
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return value if info.field_name == "message" else normalized

    @property
    def redis_session_key(self) -> str:
        """返回 Redis 中保存 Pyrogram session 的 key。"""
        return f"{SESSION_KEY_PREFIX}{self.name}"


class TelegramProviderConfig(ProviderConfig):
    """Telegram Provider 配置。"""

    api_id: int = Field(gt=0, description="Telegram API ID")
    api_hash: str = Field(description="Telegram API Hash")
    redis_url: str = Field(description="Redis 连接地址")
    accounts: list[TelegramSendAccount] = Field(min_length=1, description="发送账号列表")

    @field_validator("api_hash", "redis_url")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """校验必填文本字段。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} 不能为空")
        return normalized


class TelegramProvider(BaseProvider):
    """Telegram 消息发送 Provider 实现。"""

    name = "telegram"
    config_schema = TelegramProviderConfig

    async def execute(
        self,
        config: ProviderConfig,
    ) -> ProviderResult:
        """按账号列表发送 Telegram 消息并读取第一条回复。"""
        assert isinstance(config, TelegramProviderConfig)
        typed_config = config
        redis_client = redis_asyncio.from_url(typed_config.redis_url, decode_responses=True)
        account_results: list[dict[str, Any]] = []
        self.log(f"开始发送 Telegram 消息, 账号数 {len(typed_config.accounts)}")
        try:
            for account in typed_config.accounts:
                account_result = await self._execute_account(
                    redis_client,
                    typed_config,
                    account,
                )
                account_results.append(account_result)
        finally:
            await redis_client.aclose()

        failed_results = [item for item in account_results if item["success"] is False]
        data = {"accounts": account_results}
        if failed_results:
            self.log(
                f"Telegram 消息发送存在失败账号, 失败数 {len(failed_results)}"
            )
            return ProviderResult.fail(
                message="Telegram 消息发送存在失败账号",
                data=data,
            )
        self.log("Telegram 消息发送成功")
        return ProviderResult.ok(message="Telegram 消息发送成功", data=data)

    async def _execute_account(
        self,
        redis_client: Any,
        config: TelegramProviderConfig,
        account: TelegramSendAccount,
    ) -> dict[str, Any]:
        """执行单个账号的发送流程。"""
        client: Any | None = None
        self.log(f"开始处理 Telegram 账号 {account.name}")
        try:
            client = await self._login_and_save_session(redis_client, config, account)
            self.log(f"Telegram 账号 {account.name} 登录成功并保存 session")
            resolved_target, sent_message = await self._send_message(client, account)
            self.log(
                f"Telegram 账号 {account.name} 已发送消息, "
                f"目标 {resolved_target}, "
                f"消息 ID {getattr(sent_message, 'id', '-')}, "
                f"消息内容 {account.message}"
            )
            reply = await self._wait_for_reply(client, sent_message)
            if reply is None:
                self.log(f"Telegram 账号 {account.name} 30 秒内未收到回复")
            else:
                self.log(
                    f"Telegram 账号 {account.name} 收到回复, "
                    f"消息 ID {reply.get('id', '-')}, "
                    f"回复内容 {reply.get('text', '')}"
                )
            return {
                "success": True,
                "account": account.name,
                "session_key": account.redis_session_key,
                "target": self._target_to_data(resolved_target),
                "sent_message": self._message_to_data(sent_message),
                "reply": reply,
            }
        except Exception as exc:
            self.log(f"Telegram 账号 {account.name} 执行失败: {exc}")
            return {
                "success": False,
                "account": account.name,
                "session_key": account.redis_session_key,
                "error": str(exc),
            }
        finally:
            if client is not None:
                await client.stop()

    async def _login_and_save_session(
        self,
        redis_client: Any,
        config: TelegramProviderConfig,
        account: TelegramSendAccount,
    ) -> Any:
        """读取 session, 登录 Pyrogram Client 并保存最新 session。"""
        session_string = await redis_client.get(account.redis_session_key)
        client = Client(
            account.name,
            api_id=config.api_id,
            api_hash=config.api_hash,
            in_memory=True,
            session_string=session_string,
        )
        await client.start()
        await self._save_session(redis_client, client, account.redis_session_key)
        return client

    async def _send_message(
        self,
        client: Any,
        account: TelegramSendAccount,
    ) -> tuple[Any, Any]:
        """向目标发送消息, 必要时按会话标题解析目标。"""
        target = self._normalize_target(account.target)
        try:
            return target, await client.send_message(target, account.message)
        except Exception as direct_exc:
            if isinstance(target, int) or str(account.target).strip().startswith("@"):
                raise

            chat_id = await self._resolve_dialog_title(client, str(account.target))
            if chat_id is None:
                raise direct_exc
            return chat_id, await client.send_message(chat_id, account.message)

    async def _resolve_dialog_title(
        self,
        client: Any,
        title: str,
    ) -> int | None:
        """按会话标题查找聊天 ID。"""
        normalized_title = title.strip()
        async for dialog in client.get_dialogs(limit=200):
            chat = getattr(dialog, "chat", None)
            if chat is None:
                continue
            if getattr(chat, "title", None) == normalized_title:
                return int(getattr(chat, "id"))
        return None

    async def _wait_for_reply(
        self,
        client: Any,
        sent_message: Any,
    ) -> dict[str, Any] | None:
        """发送后 30 秒内等待第一条回复消息。"""
        chat_id = getattr(getattr(sent_message, "chat", None), "id", None)
        if chat_id is None:
            return None

        sent_message_id = int(getattr(sent_message, "id"))
        loop = asyncio.get_running_loop()
        reply_future: asyncio.Future[dict[str, Any]] = loop.create_future()

        @client.on_message(filters.chat(chat_id))
        async def handle_reply(_: Any, message: Any) -> None:
            """处理当前发送消息的第一条回复。"""
            reply_to_message = getattr(message, "reply_to_message", None)
            if getattr(reply_to_message, "id", None) != sent_message_id:
                return
            if reply_future.done():
                return
            reply_future.set_result(self._message_to_data(message))

        try:
            return await asyncio.wait_for(reply_future, timeout=REPLY_TIMEOUT_SECONDS)
        except TimeoutError:
            return None

    async def _save_session(
        self,
        redis_client: Any,
        client: Any,
        session_key: str,
    ) -> None:
        """导出并保存 Pyrogram session。"""
        session_string = client.export_session_string()
        if inspect.isawaitable(session_string):
            session_string = await session_string
        if session_string:
            await redis_client.set(session_key, session_string)

    @staticmethod
    def _normalize_target(target: int | str) -> int | str:
        """将数字字符串转换为聊天 ID。"""
        if isinstance(target, int):
            return target
        normalized = target.strip()
        if normalized.lstrip("-").isdigit():
            return int(normalized)
        return normalized

    def _message_to_data(self, message: Any) -> dict[str, Any]:
        """将 Pyrogram 消息转换为可序列化数据。"""
        text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        data: dict[str, Any] = {
            "id": int(getattr(message, "id")),
            "text": text,
            "date": self._date_to_string(getattr(message, "date", None)),
        }
        chat = getattr(message, "chat", None)
        if chat is not None:
            data["chat"] = {
                "id": getattr(chat, "id", None),
                "title": getattr(chat, "title", None),
                "username": getattr(chat, "username", None),
            }
        from_user = getattr(message, "from_user", None)
        if from_user is not None:
            data["from_user"] = {
                "id": getattr(from_user, "id", None),
                "username": getattr(from_user, "username", None),
                "first_name": getattr(from_user, "first_name", None),
            }

        parsed_json = self._parse_json(text)
        if parsed_json is not None:
            data["parsed"] = parsed_json
        return data

    @staticmethod
    def _target_to_data(target: Any) -> dict[str, Any]:
        """返回目标解析结果。"""
        return {"chat_id": target} if isinstance(target, int) else {"target": target}

    @staticmethod
    def _date_to_string(value: Any) -> str | None:
        """将日期对象转换为 ISO 字符串。"""
        if value is None:
            return None
        isoformat = getattr(value, "isoformat", None)
        if isoformat is None:
            return str(value)
        return str(isoformat())

    @staticmethod
    def _parse_json(text: str) -> Any | None:
        """尝试把回复文本解析为 JSON。"""
        stripped = text.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
