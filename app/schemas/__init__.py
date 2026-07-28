"""Schema 导出。"""

from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.execution import ExecutionOut, ExecutionStatus, TriggerType
from app.schemas.notification import NotificationOut, NotifyType
from app.schemas.provider import (
    ProviderCreate,
    ProviderInfo,
    ProviderUpdate,
)
from app.provider_plugins.contracts import ProviderResult
from app.schemas.responses import APIResponse, PageResponse
from app.schemas.task import NotifyStrategy, TaskOut

__all__ = [
    "APIResponse",
    "ExecutionOut",
    "ExecutionStatus",
    "LoginRequest",
    "NotificationOut",
    "NotifyStrategy",
    "NotifyType",
    "PageResponse",
    "ProviderCreate",
    "ProviderInfo",
    "ProviderResult",
    "ProviderUpdate",
    "TaskOut",
    "TokenResponse",
    "TriggerType",
    "UserOut",
]
