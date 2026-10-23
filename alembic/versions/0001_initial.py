"""initial schema: tasks, task_executions, system_settings

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique task identifier",
        ),
        sa.Column("name", sa.String(length=255), nullable=False, comment="Task display name"),
        sa.Column(
            "provider",
            sa.String(length=100),
            nullable=False,
            comment="Provider name used to execute the task",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Provider-specific task configuration validated against the provider schema",
        ),
        sa.Column(
            "cron_expression",
            sa.String(length=100),
            nullable=False,
            comment="Five-field cron expression controlling the schedule",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Whether the task is enabled for scheduling",
        ),
        sa.Column(
            "timeout",
            sa.Integer(),
            nullable=True,
            comment="Execution timeout in seconds; NULL uses the runtime default",
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Maximum retries after a failed execution",
        ),
        sa.Column(
            "retry_interval_seconds",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
            comment="Delay between retries in seconds",
        ),
        sa.Column(
            "notification_config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Task-level notification policy such as channels and triggering statuses",
        ),
        sa.Column(
            "next_run_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Next scheduled run time in UTC; NULL while the task is disabled",
        ),
        sa.Column(
            "last_run_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last execution start time in UTC",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation time in UTC",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update time in UTC",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint("name", name=op.f("uq_tasks_name")),
        sa.CheckConstraint("timeout IS NULL OR timeout > 0", name=op.f("ck_tasks_positive_timeout")),
        sa.CheckConstraint("max_retries >= 0", name=op.f("ck_tasks_nonnegative_retries")),
        sa.CheckConstraint(
            "retry_interval_seconds > 0", name=op.f("ck_tasks_positive_retry_interval")
        ),
    )
    op.create_index(op.f("ix_tasks_provider"), "tasks", ["provider"], unique=False)
    op.create_index(op.f("ix_tasks_enabled"), "tasks", ["enabled"], unique=False)
    op.create_index(op.f("ix_tasks_next_run_time"), "tasks", ["next_run_time"], unique=False)

    op.create_table(
        "task_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique execution identifier",
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Task this execution belongs to",
        ),
        sa.Column(
            "provider",
            sa.String(length=100),
            nullable=False,
            comment="Provider name snapshot at trigger time",
        ),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            comment="Provider configuration snapshot at trigger time",
        ),
        sa.Column(
            "trigger_type",
            sa.SmallInteger(),
            nullable=False,
            comment="What started this execution: 0 scheduled, 1 manual, 2 retry",
        ),
        sa.Column(
            "status",
            sa.SmallInteger(),
            nullable=False,
            comment="Lifecycle status: 0 pending, 1 running, 2 completed, 3 failed, 4 cancelled, 5 timeout",
        ),
        sa.Column(
            "retry_attempt",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Retry sequence number within the task run, 0 for the first attempt",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Execution metadata such as previous_execution_id",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Execution start time in UTC",
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Execution finish time in UTC",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Execution duration in milliseconds",
        ),
        sa.Column(
            "result_message", sa.Text(), nullable=True, comment="Provider result summary"
        ),
        sa.Column(
            "result_data",
            postgresql.JSONB(),
            nullable=True,
            comment="Provider structured result data",
        ),
        sa.Column(
            "logs",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Execution log entries persisted when the terminal state commits",
        ),
        sa.Column(
            "error_message", sa.Text(), nullable=True, comment="Failure summary without secrets"
        ),
        sa.Column(
            "error_traceback", sa.Text(), nullable=True, comment="Full failure traceback for diagnosis"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation time in UTC",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update time in UTC",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_executions_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_executions")),
        sa.CheckConstraint("trigger_type IN (0, 1, 2)", name=op.f("ck_task_executions_valid_trigger_type")),
        sa.CheckConstraint("status IN (0, 1, 2, 3, 4, 5)", name=op.f("ck_task_executions_valid_status")),
        sa.CheckConstraint(
            "retry_attempt >= 0", name=op.f("ck_task_executions_nonnegative_retry_attempt")
        ),
    )
    op.create_index(
        op.f("ix_task_executions_task_id"), "task_executions", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_task_executions_status"), "task_executions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_task_executions_started_at"), "task_executions", ["started_at"], unique=False
    )

    op.create_table(
        "system_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique setting identifier",
        ),
        sa.Column(
            "scope",
            sa.String(length=255),
            nullable=False,
            comment="Configuration scope such as auth or notification",
        ),
        sa.Column(
            "key",
            sa.String(length=255),
            nullable=False,
            comment="Unique configuration key within the scope",
        ),
        sa.Column(
            "type",
            sa.String(length=20),
            nullable=False,
            comment="Value type one of object, string, integer, boolean, array",
        ),
        sa.Column(
            "value",
            postgresql.JSONB(),
            nullable=False,
            comment="Configuration value, credentials redacted in responses",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Whether this setting is active",
        ),
        sa.Column(
            "description",
            sa.String(length=255),
            server_default=sa.text("''"),
            nullable=False,
            comment="Human-readable purpose",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation time in UTC",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update time in UTC",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_settings")),
        sa.UniqueConstraint("scope", "key", name="uq_system_settings_scope_key"),
        sa.CheckConstraint(
            "scope IN ('auth', 'system', 'logging', 'browser', 'notification')",
            name=op.f("ck_system_settings_valid_scope"),
        ),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index(op.f("ix_task_executions_started_at"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_status"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_task_id"), table_name="task_executions")
    op.drop_table("task_executions")
    op.drop_index(op.f("ix_tasks_next_run_time"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_enabled"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_provider"), table_name="tasks")
    op.drop_table("tasks")
