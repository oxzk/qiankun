"""数据备份应用服务。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select

from app.config.settings import settings
from app.infrastructure.database.session import Base, UTCDateTime
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.schemas.backup import BackupInfo
from app.shared.datetime import utc_now
from app.shared.errors import AppError

BACKUP_FILE_PREFIX = "qk-backup-"
"""备份文件名前缀。"""

BACKUP_FILE_SUFFIX = ".json"
"""备份文件扩展名。"""


class BackupService:
    """数据备份应用服务。"""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
        backup_dir: str | Path | None = None,
    ) -> None:
        """初始化数据备份应用服务。"""
        self._uow_factory = uow_factory
        self._backup_dir = Path(backup_dir or settings.backup_dir)

    async def list_backups(self) -> list[BackupInfo]:
        """列出备份历史。"""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        backups: list[BackupInfo] = []
        for path in self._backup_dir.glob(f"{BACKUP_FILE_PREFIX}*{BACKUP_FILE_SUFFIX}"):
            if not path.is_file():
                continue
            info = self._read_backup_info(path)
            if info is not None:
                backups.append(info)
        return sorted(backups, key=lambda item: item.created_at, reverse=True)

    async def create_backup(self) -> BackupInfo:
        """创建数据库 JSON 备份。"""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        created_at = utc_now()
        payload: dict[str, Any] = {
            "version": 1,
            "created_at": created_at.isoformat(),
            "tables": {},
        }

        async with self._uow_factory() as uow:
            if uow.session is None:
                raise RuntimeError("工作单元尚未打开")
            for table in Base.metadata.sorted_tables:
                result = await uow.session.execute(select(table))
                rows = [self._serialize_row(dict(row)) for row in result.mappings().all()]
                payload["tables"][table.name] = rows

        path = self._backup_dir / self._build_filename(created_at)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        info = self._read_backup_info(path)
        if info is None:
            raise AppError("备份文件创建失败", status_code=500)
        return info

    async def restore_backup(self, filename: str) -> bool:
        """从指定备份恢复数据库。"""
        path = self._resolve_backup_path(filename)
        payload = self._read_backup_payload(path)
        tables_payload = payload.get("tables")
        if not isinstance(tables_payload, dict):
            raise AppError("备份文件格式无效")

        table_map = {table.name: table for table in Base.metadata.sorted_tables}
        missing_tables = set(table_map) - set(tables_payload)
        if missing_tables:
            raise AppError(f"备份文件缺少表数据: {', '.join(sorted(missing_tables))}")

        async with self._uow_factory() as uow:
            if uow.session is None:
                raise RuntimeError("工作单元尚未打开")
            try:
                for table in reversed(Base.metadata.sorted_tables):
                    await uow.session.execute(delete(table))

                for table in Base.metadata.sorted_tables:
                    rows = tables_payload.get(table.name, [])
                    if not isinstance(rows, list):
                        raise AppError(f"备份表数据无效: {table.name}")
                    normalized_rows = [
                        self._deserialize_row(table_map[table.name], row)
                        for row in rows
                        if isinstance(row, dict)
                    ]
                    if normalized_rows:
                        await uow.session.execute(insert(table), normalized_rows)
                await uow.commit()
            except Exception:
                await uow.rollback()
                raise
        return True

    def _read_backup_info(self, path: Path) -> BackupInfo | None:
        """读取备份文件元信息。"""
        try:
            payload = self._read_backup_payload(path)
            created_at = self._parse_datetime(str(payload["created_at"]))
            tables = payload.get("tables", {})
            table_counts = {
                table_name: len(rows)
                for table_name, rows in tables.items()
                if isinstance(table_name, str) and isinstance(rows, list)
            } if isinstance(tables, dict) else {}
            return BackupInfo(
                filename=path.name,
                created_at=created_at,
                size_bytes=path.stat().st_size,
                table_counts=table_counts,
            )
        except Exception:
            return None

    def _read_backup_payload(self, path: Path) -> dict[str, Any]:
        """读取并解析备份文件。"""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AppError("备份文件不存在", status_code=404) from exc
        except json.JSONDecodeError as exc:
            raise AppError("备份文件格式无效") from exc
        if not isinstance(payload, dict):
            raise AppError("备份文件格式无效")
        return payload

    def _resolve_backup_path(self, filename: str) -> Path:
        """解析备份文件路径并阻止路径穿越。"""
        if Path(filename).name != filename:
            raise AppError("备份文件名无效")
        path = (self._backup_dir / filename).resolve()
        root = self._backup_dir.resolve()
        if path.parent != root:
            raise AppError("备份文件名无效")
        return path

    @staticmethod
    def _build_filename(created_at: datetime) -> str:
        """构造备份文件名。"""
        timestamp = created_at.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"{BACKUP_FILE_PREFIX}{timestamp}{BACKUP_FILE_SUFFIX}"

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        """序列化数据库行。"""
        return {
            key: BackupService._serialize_value(value)
            for key, value in row.items()
        }

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """序列化数据库字段值。"""
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.replace(tzinfo=timezone.utc).isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    @staticmethod
    def _deserialize_row(table: Any, row: dict[str, Any]) -> dict[str, Any]:
        """反序列化数据库行。"""
        normalized: dict[str, Any] = {}
        columns = {column.name: column for column in table.columns}
        for key, value in row.items():
            column = columns.get(key)
            if column is None:
                continue
            if BackupService._is_datetime_column(column) and isinstance(value, str):
                normalized[key] = BackupService._parse_datetime(value)
                continue
            normalized[key] = value
        return normalized

    @staticmethod
    def _is_datetime_column(column: Any) -> bool:
        """判断列是否为时间类型。"""
        return isinstance(column.type, UTCDateTime) or column.name.endswith("_at")

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """解析 ISO 时间字符串。"""
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
