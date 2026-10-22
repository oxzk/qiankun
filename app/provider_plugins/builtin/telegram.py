"""Telegram 消息发送 Provider。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from typing import Any

from pydantic import Field, ValidationInfo, field_validator
from pyrogram import Client, filters
from redis import asyncio as redis_asyncio

from app.provider_plugins.base import BaseProvider
from app.provider_plugins.contracts import ProviderConfig, ProviderResult
from app.shared.logger import logger

SESSION_KEY_PREFIX = "pyrogram:session:"
"""Pyrogram session 在 Redis 中的 key 前缀。"""

REPLY_TIMEOUT_SECONDS = 30.0
"""读取第一条回复的固定超时时间。"""

LOGIN_TIMEOUT_SECONDS = 30.0
"""Pyrogram 登录超时时间; 超时后结束静默重试, 让失败可见。"""

CLIENT_STOP_TIMEOUT_SECONDS = 10.0
"""关闭 Pyrogram Client 的超时时间。"""

ACCOUNT_LOCK_KEY_PREFIX = "telegram:account:lock:"
"""账号互斥锁在 Redis 中的 key 前缀。"""

ACCOUNT_LOCK_TTL_SECONDS = 300
"""账号互斥锁过期时间, 与任务超时保持一致的量级。"""

ACCOUNT_LOCK_WAIT_SECONDS = 30.0
"""等待账号互斥锁的最长时间。"""

ACCOUNT_LOCK_RETRY_INTERVAL_SECONDS = 0.5
"""账号互斥锁重试间隔。"""

RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""
"""仅当锁值匹配时才删除, 避免误删其他执行持有的锁。"""


def configure_pyrogram_logging() -> None:
    """把 Pyrogram 日志接入应用日志, 让连接重试过程可见。"""
    pyrogram_logger = logging.getLogger("pyrogram")
    if getattr(pyrogram_logger, "_qiankun_configured", False):
        return

    pyrogram_logger.setLevel(logging.INFO)
    pyrogram_logger.propagate = False
    for handler in logger.handlers:
        pyrogram_logger.addHandler(handler)

    # session 日志包含 Connecting / Session initialized / Retrying 等关键阶段。
    logging.getLogger("pyrogram.session").setLevel(logging.INFO)
    # crypto 等子模块日志过多, 保持告警级别。
    logging.getLogger("pyrogram.crypto").setLevel(logging.WARNING)
    pyrogram_logger._qiankun_configured = True  # type: ignore[attr-defined]


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
        configure_pyrogram_logging()
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
        lock_token = await self._acquire_account_lock(redis_client, account)
        if lock_token is None:
            self.log(
                f"Telegram 账号 {account.name} 获取账号锁失败, "
                f"可能有其他任务正在使用该账号"
            )
            return {
                "success": False,
                "account": account.name,
                "session_key": account.redis_session_key,
                "error": "账号正在被其他任务使用",
            }
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
                await self._stop_client(client, account.name)
            await self._release_account_lock(redis_client, account, lock_token)

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
        self.log(
            f"Telegram 账号 {account.name} 开始登录, "
            f"session {'存在' if session_string else '缺失'}, "
            f"超时 {LOGIN_TIMEOUT_SECONDS} 秒"
        )
        try:
            await asyncio.wait_for(client.start(), timeout=LOGIN_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            await self._stop_client(client, account.name)
            raise RuntimeError(
                f"登录超时: {LOGIN_TIMEOUT_SECONDS} 秒内无法连接 Telegram, "
                f"账号 {account.name}"
            ) from exc
        self.log(f"Telegram 账号 {account.name} 登录完成")
        await self._save_session(redis_client, client, account.redis_session_key)
        return client

    async def _stop_client(self, client: Any, account_name: str) -> None:
        """关闭 Client, 失败不掩盖原始异常。"""
        try:
            await asyncio.wait_for(
                client.stop(),
                timeout=CLIENT_STOP_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            self.log(f"Telegram 账号 {account_name} 关闭客户端异常: {type(exc).__name__}: {exc}")

    async def _acquire_account_lock(
        self,
        redis_client: Any,
        account: TelegramSendAccount,
    ) -> str | None:
        """获取账号互斥锁, 避免同一账号被多个任务并发登录。"""
        lock_key = f"{ACCOUNT_LOCK_KEY_PREFIX}{account.name}"
        token = uuid.uuid4().hex
        deadline = asyncio.get_running_loop().time() + ACCOUNT_LOCK_WAIT_SECONDS
        while True:
            acquired = await redis_client.set(
                lock_key,
                token,
                nx=True,
                ex=ACCOUNT_LOCK_TTL_SECONDS,
            )
            if acquired:
                self.log(
                    f"Telegram 账号 {account.name} 已获取账号锁, "
                    f"TTL {ACCOUNT_LOCK_TTL_SECONDS} 秒"
                )
                return token
            if asyncio.get_running_loop().time() >= deadline:
                return None
            await asyncio.sleep(ACCOUNT_LOCK_RETRY_INTERVAL_SECONDS)

    async def _release_account_lock(
        self,
        redis_client: Any,
        account: TelegramSendAccount,
        token: str,
    ) -> None:
        """释放账号互斥锁, 仅删除自己持有的锁。"""
        lock_key = f"{ACCOUNT_LOCK_KEY_PREFIX}{account.name}"
        try:
            await redis_client.eval(RELEASE_LOCK_SCRIPT, 1, lock_key, token)
            self.log(f"Telegram 账号 {account.name} 已释放账号锁")
        except Exception as exc:
            self.log(
                f"Telegram 账号 {account.name} 释放账号锁失败: "
                f"{type(exc).__name__}: {exc}"
            )

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
        self.log(f"开始遍历 Telegram Dialog, 目标标题: {normalized_title!r}")
        dialog_count = 0
        matched_chat_id: int | None = None
        async for dialog in client.get_dialogs(limit=200):
            chat = getattr(dialog, "chat", None)
            if chat is None:
                continue
            dialog_count += 1
            chat_id = getattr(chat, "id", None)
            chat_title = getattr(chat, "title", None)
            chat_username = getattr(chat, "username", None)
            chat_type = getattr(chat, "type", None)
            self.log(
                f"[Dialog #{dialog_count}] chat_id={chat_id} | "
                f"type={chat_type} | "
                f"title={chat_title!r} | "
                f"username={chat_username!r}"
            )
            if chat_title == normalized_title:
                matched_chat_id = int(chat_id)
                self.log(
                    f"匹配到会话: 标题={normalized_title!r}, chat_id={matched_chat_id}"
                )
        self.log(f"Dialog 遍历完成, 共 {dialog_count} 个会话")
        if matched_chat_id is None:
            self.log(f"未找到目标会话: {normalized_title!r}")
        else:
            self.log(f"最终匹配 chat_id: {matched_chat_id}")
        return matched_chat_id

    async def _wait_for_reply(
        self,
        client: Any,
        sent_message: Any,
    ) -> dict[str, Any] | None:
        """发送后 30 秒内等待第一条回复消息。

        优先匹配引用了发送消息的回复; 对方若直接发送新消息 (不引用),
        则按同会话首条来消息处理。
        """
        chat_id = getattr(getattr(sent_message, "chat", None), "id", None)
        if chat_id is None:
            self.log("等待回复跳过: 发送结果缺少 chat.id")
            return None

        sent_message_id = int(getattr(sent_message, "id"))
        loop = asyncio.get_running_loop()
        reply_future: asyncio.Future[dict[str, Any]] = loop.create_future()

        self.log(
            f"开始等待回复: chat_id={chat_id}, 发送消息 ID={sent_message_id}, "
            f"超时={REPLY_TIMEOUT_SECONDS} 秒"
        )

        @client.on_message(filters.chat(chat_id))
        async def handle_reply(_: Any, message: Any) -> None:
            """处理当前发送消息的回复。"""
            reply_to_message = getattr(message, "reply_to_message", None)
            reply_to_message_id = getattr(reply_to_message, "id", None)
            message_id = getattr(message, "id", "-")
            outgoing = getattr(message, "outgoing", False)
            message_text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
            self.log(
                f"收到会话消息: 消息 ID={message_id}, "
                f"outgoing={outgoing}, "
                f"reply_to_message_id={reply_to_message_id}, "
                f"内容 {message_text[:100]!r}"
            )
            if outgoing:
                self.log(f"忽略消息: 消息 ID={message_id} 是自己发送的消息")
                return
            if reply_future.done():
                self.log(f"忽略消息: 已收到过回复, 消息 ID={message_id}")
                return
            if reply_to_message_id == sent_message_id:
                self.log(f"匹配到回复: 消息 ID={message_id}, 引用了发送消息")
            else:
                self.log(
                    f"接受为回复: 消息 ID={message_id}, "
                    f"未引用发送消息 (reply_to_message_id={reply_to_message_id}), "
                    f"按同会话首条来消息处理"
                )
            reply_future.set_result(self._message_to_data(message))

        try:
            reply = await asyncio.wait_for(reply_future, timeout=REPLY_TIMEOUT_SECONDS)
            self.log(f"等待回复结束: 已收到回复, 消息 ID={reply.get('id', '-')}")
            return reply
        except TimeoutError:
            self.log(
                f"等待回复超时: chat_id={chat_id}, 发送消息 ID={sent_message_id}, "
                f"{REPLY_TIMEOUT_SECONDS} 秒内没有收到匹配的回复"
            )
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
