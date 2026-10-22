"""Provider 数据库模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base, UTCDateTime
from app.shared.datetime import utc_now


class Provider(Base):
    """Provider 表。"""

    __tablename__ = "qk_providers"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_qk_providers_name"),
        Index("idx_qk_providers_name", "name"),
        Index("idx_qk_providers_enabled", "enabled"),
    )
