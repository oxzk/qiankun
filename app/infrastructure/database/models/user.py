"""用户数据库模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base, UTCDateTime
from app.shared.datetime import utc_now


class User(Base):
    """用户表。"""

    __tablename__ = "qk_users"

    id: Mapped[int | None] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
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

    __table_args__ = (Index("idx_qk_users_username", "username"),)
