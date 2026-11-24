"""Sliding window rate limiter using Redis (with in-memory fallback).

Supports per-client sliding window rate limiting.
If Redis is not available or disconnected, falls back transparently
to an in-memory sliding window deque.
"""

from __future__ import annotations

import collections
import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from lakenterprises.config import get_settings

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Sliding-window rate limiter using Redis sorted sets or in-memory fallback."""

    def __init__(
        self,
        redis_client: Optional[object] = None,
        default_limit: int = 60,
        default_window_seconds: int = 60,
    ) -> None:
        self.default_limit = default_limit
        self.default_window_seconds = default_window_seconds
        self._redis = redis_client
        self._memory_store: dict[str, collections.deque] = collections.defaultdict(
            collections.deque
        )

    def is_allowed(
        self,
        key: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> tuple[bool, dict[str, int]]:
        """Check if *key* is within rate limits.

        Returns (is_allowed, info_dict) where info_dict has:
        - "limit": max allowed requests
        - "remaining": requests left in window
        - "reset": seconds until window resets
        """
        max_requests = limit if limit is not None else self.default_limit
        window = (
            window_seconds
            if window_seconds is not None
            else self.default_window_seconds
        )
        now = time.time()

        if self._redis is not None:
            try:
                return self._check_redis(key, now, max_requests, window)
            except Exception as e:
                logger.warning(
                    "Redis rate limiter error, falling back to in-memory: %s", e
                )

        return self._check_memory(key, now, max_requests, window)

    def _check_redis(
        self, key: str, now: float, limit: int, window: int
    ) -> tuple[bool, dict[str, int]]:
        redis_key = f"rate_limit:{key}"
        clear_before = now - window

        # Pipeline operations for atomicity
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, clear_before)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window + 1)
        results = pipe.execute()

        current_count = results[1]
        allowed = current_count < limit
        remaining = max(0, limit - current_count - (1 if allowed else 0))
        reset_seconds = int(window)

        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_seconds,
        }

    def _check_memory(
        self, key: str, now: float, limit: int, window: int
    ) -> tuple[bool, dict[str, int]]:
        q = self._memory_store[key]
        clear_before = now - window

        while q and q[0] <= clear_before:
            q.popleft()

        current_count = len(q)
        if current_count < limit:
            q.append(now)
            allowed = True
            remaining = limit - current_count - 1
        else:
            allowed = False
            remaining = 0

        oldest = q[0] if q else now
        reset_seconds = max(1, int(window - (now - oldest)))

        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_seconds,
        }

    def reset(self, key: Optional[str] = None) -> None:
        """Clear rate limit entries (for testing)."""
        if key:
            self._memory_store.pop(key, None)
            if self._redis is not None:
                try:
                    self._redis.delete(f"rate_limit:{key}")
                except Exception:
                    pass
        else:
            self._memory_store.clear()
            if self._redis is not None:
                try:
                    keys = self._redis.keys("rate_limit:*")
                    if keys:
                        self._redis.delete(*keys)
                except Exception:
                    pass


# Global singleton
_limiter: Optional[SlidingWindowRateLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return the global rate limiter instance."""
    global _limiter
    if _limiter is None:
        settings = get_settings()
        redis_conn = None
        if settings.cache_store == "redis" and settings.redis_url:
            try:
                import redis

                client = redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                redis_conn = client
            except Exception as e:
                logger.info("Redis not reachable (%s), using in-memory rate limiter", e)

        _limiter = SlidingWindowRateLimiter(
            redis_client=redis_conn,
            default_limit=settings.rate_limit_per_minute,
            default_window_seconds=60,
        )
    return _limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces rate limiting per client IP or user."""

    def __init__(
        self,
        app: object,
        limiter: Optional[SlidingWindowRateLimiter] = None,
        exempt_paths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or get_rate_limiter()
        self.exempt_paths = exempt_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        for exempt in self.exempt_paths:
            if request.url.path.startswith(exempt):
                return await call_next(request)

        # Identify client key: user ID if authenticated header or client IP
        client_key = request.headers.get("X-User-ID")
        if not client_key:
            client_key = request.client.host if request.client else "127.0.0.1"

        allowed, info = self.limiter.is_allowed(client_key)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Try again in {info['reset']} seconds."
                },
                headers={
                    "Retry-After": str(info["reset"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        return response
