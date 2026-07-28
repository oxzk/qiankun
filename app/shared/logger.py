"""日志工具模块。"""

from __future__ import annotations

import logging


def build_logger(name: str = "qiankun") -> logging.Logger:
    """构建应用日志实例。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = build_logger()
"""全局日志实例。"""
