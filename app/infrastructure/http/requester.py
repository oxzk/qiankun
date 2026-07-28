"""异步 HTTP 请求模块。"""

from __future__ import annotations

from typing import Any

from curl_cffi import requests

from app.config.settings import settings
from app.shared.retry import async_retry
from app.shared.logger import logger


class RetryableRequestError(Exception):
    """可重试 HTTP 响应异常。"""

    def __init__(self, response: requests.Response) -> None:
        """初始化可重试 HTTP 响应异常。"""
        self.response = response
        super().__init__(f"HTTP {response.status_code}: {response.url}")


class Requester:
    """管理可复用异步 HTTP 客户端会话和重试请求流程。"""

    DEFAULT_TIMEOUT = 20
    """默认请求超时时间。"""

    def __init__(
        self,
        *,
        client: requests.AsyncSession | None = None,
        timeout: float | None = None,
        retry_attempts: int | None = None,
        retry_delay_seconds: float | None = None,
        retry_backoff: float | None = None,
    ) -> None:
        """初始化请求器。"""
        self._client = client
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._retry_attempts = retry_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._retry_backoff = retry_backoff

    @property
    def client(self) -> requests.AsyncSession:
        """获取或创建 curl-cffi 客户端会话。"""
        if self._client is None:
            self._client = requests.AsyncSession(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端会话。"""
        if self._client is not None:
            client = self._client
            self._client = None
            await client.close()

    async def request(
        self,
        method: str,
        url: str,
        *,
        raise_for_status: bool = True,
        retry_on_status: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        """发送 HTTP 请求并对可恢复失败执行重试。"""
        request_method = method.upper()
        request_kwargs = self._build_request_kwargs(**kwargs)
        request_with_retry = async_retry(
            attempts=self._normalized_retry_attempts(),
            delay_seconds=self._normalized_retry_delay_seconds(),
            backoff=self._normalized_retry_backoff(),
            retry_exceptions=(
                requests.RequestsError,
                RetryableRequestError,
            ),
        )(self._request_once)

        try:
            response = await request_with_retry(
                request_method,
                url,
                request_kwargs,
                retry_on_status,
            )
        except RetryableRequestError as exc:
            if not raise_for_status:
                return exc.response
            exc.response.raise_for_status()
            raise
        except Exception as exc:
            logger.warning("HTTP 请求失败: %s %s: %s", request_method, url, exc)
            raise

        if raise_for_status:
            response.raise_for_status()
        return response

    async def post_json(
        self,
        url: str,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """发送 JSON POST 请求。"""
        return await self.request("POST", url, json=json, headers=headers or {})

    async def _request_once(
        self,
        method: str,
        url: str,
        request_kwargs: dict[str, Any],
        retry_on_status: bool,
    ) -> requests.Response:
        """执行单次 HTTP 请求。"""
        response = await self.client.request(method, url, **request_kwargs)
        if retry_on_status and (response.status_code == 429 or response.status_code >= 500):
            # 429 和 5xx 通常代表临时性失败, 延迟重试比立即失败更适合通知发送场景。
            raise RetryableRequestError(response)
        return response

    def _build_request_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        """构建 curl-cffi 请求参数。"""
        request_kwargs = dict(kwargs)
        if "follow_redirects" in request_kwargs:
            request_kwargs["allow_redirects"] = request_kwargs.pop("follow_redirects")
        request_kwargs.setdefault("timeout", self._timeout)
        return request_kwargs

    def _normalized_retry_attempts(self) -> int:
        """返回规范化后的 HTTP 请求最大尝试次数。"""
        return max(1, self._retry_attempts or settings.http_retry_attempts)

    def _normalized_retry_delay_seconds(self) -> float:
        """返回规范化后的 HTTP 请求重试初始延迟秒数。"""
        if self._retry_delay_seconds is None:
            return max(0.0, settings.http_retry_delay_seconds)
        return max(0.0, self._retry_delay_seconds)

    def _normalized_retry_backoff(self) -> float:
        """返回规范化后的 HTTP 请求重试退避倍数。"""
        if self._retry_backoff is None:
            return max(1.0, settings.http_retry_backoff)
        return max(1.0, self._retry_backoff)
