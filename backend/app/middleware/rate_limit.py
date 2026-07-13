"""API 限流中间件 - 滑动窗口限流，保护后端 API 不被滥用"""
from __future__ import annotations

import time
import asyncio
from collections import defaultdict
from fastapi import Request
from app.config import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from app.exceptions import ErrorCode, ERROR_MESSAGES
from app.models.schemas import ErrorResponse


class RateLimiter:
    """基于滑动窗口的 IP 限流器"""

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock: asyncio.Lock = asyncio.Lock()
        self._last_cleanup: float = time.time()

    async def is_allowed(self, client_ip: str) -> bool:
        """检查指定 IP 是否允许请求"""
        now: float = time.time()

        async with self._lock:
            # 定期清理过期记录
            if now - self._last_cleanup > 300:  # 每 5 分钟清理一次
                self._cleanup_expired(now)
                self._last_cleanup = now

            # 清理当前 IP 的过期记录
            window_start: float = now - self.window_seconds
            self._requests[client_ip] = [
                ts for ts in self._requests[client_ip] if ts > window_start
            ]

            if len(self._requests[client_ip]) >= self.max_requests:
                return False

            self._requests[client_ip].append(now)
            return True

    def _cleanup_expired(self, now: float) -> None:
        """清理所有过期记录"""
        window_start: float = now - self.window_seconds
        expired_ips: list[str] = []
        for ip, timestamps in self._requests.items():
            self._requests[ip] = [ts for ts in timestamps if ts > window_start]
            if not self._requests[ip]:
                expired_ips.append(ip)
        for ip in expired_ips:
            del self._requests[ip]


_rate_limiter: RateLimiter = RateLimiter()


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    forwarded: str | None = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(request: Request) -> None:
    """检查限流，超限时抛出异常"""
    client_ip: str = get_client_ip(request)
    if not await _rate_limiter.is_allowed(client_ip):
        raise RateLimitExceededError(client_ip)


class RateLimitExceededError(Exception):
    """限流超限异常"""
    client_ip: str

    def __init__(self, client_ip: str) -> None:
        self.client_ip = client_ip
        super().__init__(f"请求过于频繁: {client_ip}")


def build_rate_limit_response() -> dict[str, object]:
    """构建 429 限流响应"""
    error_code: ErrorCode = ErrorCode.RATE_LIMIT_EXCEEDED
    return ErrorResponse(
        error_code=error_code.value,
        message=ERROR_MESSAGES[error_code],
        detail=f"超过 {RATE_LIMIT_MAX_REQUESTS} 次/{RATE_LIMIT_WINDOW_SECONDS}秒 限制",
    ).model_dump()
