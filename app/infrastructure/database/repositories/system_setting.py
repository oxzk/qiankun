"""System settings queries."""

from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.database.models.system_setting import SystemSetting
from app.infrastructure.database.repositories.base import Repository


class SystemSettingRepository(Repository[SystemSetting]):
    """Settings keyed by (scope, key)."""

    model = SystemSetting

    async def by_key(self, scope: str, key: str) -> SystemSetting | None:
        """Fetch one row or None."""
        rows = await self.session.execute(
            select(SystemSetting).where(SystemSetting.scope == scope, SystemSetting.key == key)
        )
        found: SystemSetting | None = rows.scalars().first()
        return found

    async def list_scope(self, scope: str | None = None) -> list[SystemSetting]:
        """All settings, optionally filtered by scope, stable ordering."""
        query = select(SystemSetting)
        if scope is not None:
            query = query.where(SystemSetting.scope == scope)
        query = query.order_by(SystemSetting.scope.asc(), SystemSetting.key.asc())
        return list((await self.session.execute(query)).scalars().all())

    async def list(  # type: ignore[override]
        self,
        offset: int,
        limit: int,
        *filters: object,
        scope: str | None = None,
    ) -> tuple[list[SystemSetting], int]:
        """One page of settings with the total count, scope-filtered."""
        from sqlalchemy import func

        conditions = []
        if scope is not None:
            conditions.append(SystemSetting.scope == scope)
        rows = await self.session.execute(
            select(SystemSetting)
            .where(*conditions)
            .order_by(SystemSetting.scope.asc(), SystemSetting.key.asc())
            .offset(offset)
            .limit(limit)
        )
        items = list(rows.scalars().all())
        total = (
            await self.session.execute(
                select(func.count()).select_from(SystemSetting).where(*conditions)
            )
        ).scalar_one()
        return items, total
