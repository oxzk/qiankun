"""初始化数据库结构。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "202607070001"
"""迁移版本号。"""

down_revision: str | None = None
"""上一迁移版本号。"""

branch_labels: str | Sequence[str] | None = None
"""迁移分支标签。"""

depends_on: str | Sequence[str] | None = None
"""迁移依赖版本。"""


DEFAULT_ADMIN_PASSWORD_HASH = "$2b$12$HLEf3HYZcusDBTH7L3BriuxfA35m8eEBNu91mEJlhiV/wCikIGrGm"
"""默认管理员 admin 密码的 bcrypt 哈希。"""


def _seed_admin_user(password_hash: str) -> None:
    """写入初始管理员用户。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        sa.table(
            "qk_users",
            sa.column("username", sa.String(length=50)),
            sa.column("password", sa.String(length=255)),
            sa.column("created_at", sa.TIMESTAMP()),
            sa.column("updated_at", sa.TIMESTAMP()),
        ),
        [
            {
                "username": "admin",
                "password": password_hash,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def upgrade() -> None:
    """创建应用初始数据库表。"""
    op.create_table(
        "qk_notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("notify_type", sa.Enum("webhook", "telegram", native_enum=False, length=50), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qk_notifications_enabled", "qk_notifications", ["enabled"])
    op.create_index("idx_qk_notifications_notify_type", "qk_notifications", ["notify_type"])

    op.create_table(
        "qk_providers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_qk_providers_name"),
    )
    op.create_index("idx_qk_providers_enabled", "qk_providers", ["enabled"])
    op.create_index("idx_qk_providers_name", "qk_providers", ["name"])

    op.create_table(
        "qk_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("provider_config", sa.JSON(), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("retry_interval", sa.Integer(), nullable=False),
        sa.Column("notification_ids", sa.JSON(), nullable=True),
        sa.Column("notify_strategy", sa.Enum("never", "always", "on_failure", "on_success", native_enum=False, length=20), nullable=False),
        sa.Column("next_run_time", sa.TIMESTAMP(), nullable=True),
        sa.Column("last_run_time", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qk_tasks_enabled", "qk_tasks", ["enabled"])
    op.create_index("idx_qk_tasks_next_run_time", "qk_tasks", ["next_run_time"])
    op.create_index("idx_qk_tasks_provider_name", "qk_tasks", ["provider_name"])

    op.create_table(
        "qk_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_qk_users_username", "qk_users", ["username"])
    _seed_admin_user(DEFAULT_ADMIN_PASSWORD_HASH)

    op.create_table(
        "qk_task_executions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("provider_config", sa.JSON(), nullable=False),
        sa.Column("trigger_type", sa.Enum("auto", "manual", native_enum=False, length=20), nullable=False),
        sa.Column("status", sa.Enum("running", "success", "failed", "timeout", "cancelled", native_enum=False, length=20), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_attempt", sa.Integer(), nullable=False),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["qk_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_qk_task_executions_started_at", "qk_task_executions", ["started_at"])
    op.create_index("idx_qk_task_executions_status", "qk_task_executions", ["status"])
    op.create_index("idx_qk_task_executions_task_id", "qk_task_executions", ["task_id"])


def downgrade() -> None:
    """删除应用初始数据库表。"""
    op.drop_index("idx_qk_task_executions_task_id", table_name="qk_task_executions")
    op.drop_index("idx_qk_task_executions_status", table_name="qk_task_executions")
    op.drop_index("idx_qk_task_executions_started_at", table_name="qk_task_executions")
    op.drop_table("qk_task_executions")

    op.drop_index("idx_qk_users_username", table_name="qk_users")
    op.drop_table("qk_users")

    op.drop_index("idx_qk_tasks_provider_name", table_name="qk_tasks")
    op.drop_index("idx_qk_tasks_next_run_time", table_name="qk_tasks")
    op.drop_index("idx_qk_tasks_enabled", table_name="qk_tasks")
    op.drop_table("qk_tasks")

    op.drop_index("idx_qk_providers_name", table_name="qk_providers")
    op.drop_index("idx_qk_providers_enabled", table_name="qk_providers")
    op.drop_table("qk_providers")

    op.drop_index("idx_qk_notifications_notify_type", table_name="qk_notifications")
    op.drop_index("idx_qk_notifications_enabled", table_name="qk_notifications")
    op.drop_table("qk_notifications")
