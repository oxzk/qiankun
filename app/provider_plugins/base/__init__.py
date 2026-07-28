"""Provider 基础能力。"""

import inspect
from types import ModuleType

from app.shared.errors import AppError
from app.provider_plugins.base.browser_provider import BaseBrowserProvider
from app.provider_plugins.base.camoufox import BaseCamoufox
from app.provider_plugins.base.discuz import (
    DISCUZ_USER_AGENT,
    DiscuzForum,
)
from app.provider_plugins.base.provider import BaseProvider
from app.provider_plugins.base.turnstile import (
    TurnstileDetector,
    TurnstileHandler,
    TurnstileSnapshot,
)

__all__ = [
    "BaseBrowserProvider",
    "BaseCamoufox",
    "BaseProvider",
    "DEFAULT_FORUM_USER_AGENT",
    "DISCUZ_USER_AGENT",
    "DiscuzForum",
    "ForumClient",
    "TurnstileDetector",
    "TurnstileHandler",
    "TurnstileSnapshot",
    "find_single_provider_class",
]

ForumClient = DiscuzForum
"""论坛通用客户端封装。"""

DEFAULT_FORUM_USER_AGENT = DISCUZ_USER_AGENT
"""论坛请求默认浏览器标识。"""


def find_single_provider_class(
    module: ModuleType,
    module_name: str,
    label: str = "Provider",
) -> type[BaseProvider]:
    """从模块中查找唯一的 BaseProvider 子类。"""
    provider_classes = [
        member
        for _, member in inspect.getmembers(module, inspect.isclass)
        if member.__module__ == module_name
        and issubclass(member, BaseProvider)
        and member not in {BaseProvider, BaseBrowserProvider}
        and not inspect.isabstract(member)
    ]
    if not provider_classes:
        raise AppError(f"{label}未定义 Provider 类")
    if len(provider_classes) > 1:
        raise AppError(f"{label}定义了多个 Provider 类")
    return provider_classes[0]
