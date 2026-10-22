"""请求日志中间件。"""

from __future__ import annotations

import time

from fastapi import Request

from app.shared.logger import logger


async def log_requests(request: Request, call_next):
    """记录 HTTP 请求耗时。"""
    start_time = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(
        "%s %s -> %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response
