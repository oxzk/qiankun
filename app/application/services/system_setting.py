"""System settings with idempotent bootstrap and credential redaction."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.application.pagination import Page, paginate
from app.core.config import LoggingSettings, SystemBaseSettings
from app.core.exceptions import ValidationError
from app.infrastructure.auth.password import hash_password
from app.infrastructure.database.models.system_setting import SystemSetting

AUTH_SCOPE = "auth"
"""Administrator credential scope."""

AUTH_KEY = "admin"
"""Administrator credential key."""

REDACTED = "[REDACTED]"
"""Placeholder returned instead of secret values."""

SECRET_FIELDS = frozenset({"password", "bot_token", "token", "api_key"})
"""Keys whose values never leave the process."""

STATIC_DEFAULTS: tuple[tuple[str, str, dict[str, Any], str], ...] = (
    ("browser", "cdp", {"enabled": False, "endpoint": "", "token": ""}, "远程 CDP 浏览器连接"),
    ("notification", "telegram", {"enabled": False, "bot_token": "", "chat_id": ""}, "TG 通知渠道"),
    ("notification", "webhook", {"enabled": False, "url": ""}, "Webhook 通知渠道"),
)

SETTING_SCHEMAS: dict[tuple[str, str], type[BaseModel]] = {
    ("system", "base"): SystemBaseSettings,
    ("logging", "loguru"): LoggingSettings,
}
"""Rows whose value must validate against a schema on every write."""

RESTART_KEYS: frozenset[tuple[str, str]] = frozenset({("system", "base")})
"""Rows applied only at startup; their updates flag restart_required."""


class SystemSettingService:
    """Transactional settings access; response redaction happens here."""

    def __init__(self, uow_factory: Any) -> None:
        """Keep the UoW factory; the update hook is wired by the container."""
        self.uow_factory = uow_factory
        self._updates = asyncio.Lock()
        self.on_update: Any = None

    async def bootstrap(
        self,
        admin_password_hash: str,
        system_base: dict[str, Any],
        logging_loguru: dict[str, Any],
    ) -> None:
        """Insert defaults once; fill pre-migration empty rows; never overwrite edits."""
        seeded: tuple[tuple[str, str, dict[str, Any], str], ...] = (
            ("system", "base", system_base, "系统基础配置 (调度与执行参数, 重启生效)"),
            ("logging", "loguru", logging_loguru, "日志输出与保留策略 (保存后热更新)"),
            *STATIC_DEFAULTS,
        )
        async with self.uow_factory() as uow:
            for scope, key, value, description in seeded:
                row = await uow.system_settings.by_key(scope, key)
                if row is None:
                    await uow.system_settings.add(
                        {
                            "scope": scope,
                            "key": key,
                            "type": "object",
                            "value": value,
                            "enabled": True,
                            "description": description,
                        }
                    )
                elif not (isinstance(row.value, dict) and row.value):
                    await uow.system_settings.update(row, {"value": dict(value)})
            admin = await uow.system_settings.by_key(AUTH_SCOPE, AUTH_KEY)
            if admin is None:
                await uow.system_settings.add(
                    {
                        "scope": AUTH_SCOPE,
                        "key": AUTH_KEY,
                        "type": "object",
                        "value": {"username": "admin", "password": admin_password_hash},
                        "enabled": True,
                        "description": "管理员凭证 (Argon2id)",
                    }
                )

    async def list(
        self, page: int, page_size: int, scope: str | None = None
    ) -> Page[SystemSetting]:
        """One redacted page of settings."""
        async with self.uow_factory() as uow:
            rows, total = await uow.system_settings.list(
                (page - 1) * page_size, page_size, scope=scope
            )
        items = [_redact_row(row) for row in rows]
        return paginate(items, total, page, page_size)  # type: ignore[arg-type]

    async def get(self, scope: str, key: str) -> dict[str, Any]:
        """One redacted setting or 404."""
        async with self.uow_factory() as uow:
            row = await uow.system_settings.by_key(scope, key)
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("系统配置不存在")
        return _redact_row(row)

    async def put(self, scope: str, key: str, values: dict[str, Any]) -> dict[str, Any]:
        """Validate type/value, merge redacted placeholders, persist."""
        expected = {"object": dict, "string": str, "integer": int, "boolean": bool, "array": list}
        if (
            values.get("type") not in expected
            or type(values.get("value")) is not expected[values["type"]]
        ):
            raise ValidationError("系统配置的 type 与 value 不匹配")
        self._validate_schema(scope, key, values)
        async with self._updates:
            async with self.uow_factory() as uow:
                row = await uow.system_settings.by_key(scope, key)
                stored = values["value"]
                if isinstance(stored, dict):
                    stored = await self._merge_secrets(row, stored)
                if row is None:
                    row = await uow.system_settings.add(
                        {
                            "scope": scope,
                            "key": key,
                            "type": values["type"],
                            "value": stored,
                            "enabled": bool(values.get("enabled", True)),
                            "description": str(values.get("description", "")),
                        }
                    )
                else:
                    row = await uow.system_settings.update(
                        row,
                        {
                            "type": values["type"],
                            "value": stored,
                            "enabled": bool(values.get("enabled", True)),
                            "description": str(values.get("description", row.description)),
                        },
                    )
                result = _redact_row(row)
        if self.on_update is not None:
            await self.on_update(scope, key)
        if (scope, key) in RESTART_KEYS:
            result["restart_required"] = True
        return result

    def _validate_schema(self, scope: str, key: str, values: dict[str, Any]) -> None:
        """Reject malformed writes for rows governed by a schema."""
        schema = SETTING_SCHEMAS.get((scope, key))
        if schema is None:
            return
        if values.get("type") != "object" or not isinstance(values.get("value"), dict):
            raise ValidationError("该配置必须为 object 类型")
        try:
            schema.model_validate(values["value"])
        except PydanticValidationError as error:
            problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
            raise ValidationError("配置校验失败", {"problems": problems}) from error

    async def _merge_secrets(self, row: Any, incoming: dict[str, Any]) -> dict[str, Any]:
        """Keep stored secrets when the client echoes the placeholder."""
        if row is None:
            return incoming
        stored_value = dict(row.value or {})
        merged: dict[str, Any] = {}
        for key, value in incoming.items():
            if key in SECRET_FIELDS and value == REDACTED:
                merged[key] = stored_value.get(key, "")
            elif key == "password" and stored_value.get("password", "").startswith("$argon2"):
                merged[key] = stored_value["password"]
            else:
                merged[key] = value
        for key in incoming:
            if key == "password" and merged[key] and not str(merged[key]).startswith("$argon2"):
                merged[key] = hash_password(str(merged[key]))
        return merged


def _redact_row(row: SystemSetting) -> dict[str, Any]:
    """Strip secrets from one row for the API."""
    value = row.value
    if isinstance(value, dict):
        value = {k: (REDACTED if k in SECRET_FIELDS and v else v) for k, v in value.items()}
    return {
        "scope": row.scope,
        "key": row.key,
        "type": row.type,
        "value": value,
        "enabled": row.enabled,
        "description": row.description,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
