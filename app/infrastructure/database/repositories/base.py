"""Generic repository with flush-only writes, commits belong to the UnitOfWork."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import ColumnExpressionArgument, func, select

from app.infrastructure.database.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository[G: Base]:
    """CRUD operations shared by all tables."""

    model: type[Base]

    def __init__(self, session: Any) -> None:  # AsyncSession, typed loosely to stay import-light
        """Bind the session owned by the current UnitOfWork."""
        self.session = session

    async def get(self, id: UUID, *, lock: bool = False) -> Base | None:
        """Fetch by primary key with an optional row lock."""
        query = select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        if lock:
            query = query.with_for_update()
        row: Base | None = (await self.session.execute(query)).scalar_one_or_none()
        return row

    async def add(self, values: dict[str, Any]) -> Base:
        """Insert and refresh so database defaults are visible."""
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: Base, values: dict[str, Any]) -> Base:
        """Apply a partial update and refresh database-managed columns."""
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: Base) -> None:
        """Remove the row; cascades are declared on foreign keys."""
        await self.session.delete(instance)
        await self.session.flush()

    async def list(
        self,
        offset: int,
        limit: int,
        *filters: ColumnExpressionArgument[bool],
        order_by: Sequence[ColumnExpressionArgument[Any]] | None = None,
    ) -> tuple[Sequence[Base], int]:
        """Return one page plus the total count for the same filters."""
        conditions = [condition for condition in filters if condition is not None]
        query = select(self.model).where(*conditions)
        if order_by:
            query = query.order_by(*order_by)
        else:
            query = query.order_by(
                self.model.created_at.desc(),  # type: ignore[attr-defined]
                self.model.id.desc(),  # type: ignore[attr-defined]
            )
        rows = (await self.session.execute(query.offset(offset).limit(limit))).scalars().all()
        total = (
            await self.session.execute(
                select(func.count()).select_from(self.model).where(*conditions)
            )
        ).scalar_one()
        return rows, total
