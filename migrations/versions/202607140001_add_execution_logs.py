"""新增执行记录日志字段。"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607140001"
"""迁移版本号。"""

down_revision: str | None = "202607070001"
"""上一迁移版本号。"""

branch_labels: str | Sequence[str] | None = None
"""迁移分支标签。"""

depends_on: str | Sequence[str] | None = None
"""迁移依赖版本。"""


def upgrade() -> None:
    """为执行记录表新增日志字段。"""
    op.add_column("qk_task_executions", sa.Column("logs", sa.JSON(), nullable=True))
    op.execute(sa.text("UPDATE qk_task_executions SET logs = JSON_ARRAY() WHERE logs IS NULL"))
    op.alter_column("qk_task_executions", "logs", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    """删除执行记录日志字段。"""
    op.drop_column("qk_task_executions", "logs")
