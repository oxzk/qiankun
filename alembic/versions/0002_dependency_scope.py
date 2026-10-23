"""allow the dependencies scope in system_settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_system_settings_valid_scope"
"""Literal constraint name created by the initial migration."""

WITH_DEPENDENCIES = (
    "scope IN ('auth', 'system', 'logging', 'browser', 'notification', 'dependencies')"
)
WITHOUT_DEPENDENCIES = (
    "scope IN ('auth', 'system', 'logging', 'browser', 'notification')"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE system_settings DROP CONSTRAINT {CONSTRAINT_NAME}")
    op.execute(
        f"ALTER TABLE system_settings ADD CONSTRAINT {CONSTRAINT_NAME} "
        f"CHECK ({WITH_DEPENDENCIES})"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE system_settings DROP CONSTRAINT {CONSTRAINT_NAME}")
    op.execute(
        f"ALTER TABLE system_settings ADD CONSTRAINT {CONSTRAINT_NAME} "
        f"CHECK ({WITHOUT_DEPENDENCIES})"
    )
