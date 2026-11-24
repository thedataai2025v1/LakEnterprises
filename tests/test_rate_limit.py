"""Tests for SlidingWindowRateLimiter and RateLimitMiddleware."""

import time

import fakeredis
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from lakenterprises.auth.rate_limit import (RateLimitMiddleware,
                                            SlidingWindowRateLimiter)

# ---------------------------------------------------------------------------
# Unit tests: In-memory sliding window
# ---------------------------------------------------------------------------


class TestInMemorySlidingWindow:
    def test_allows_under_limit(self):
        limiter = SlidingWindowRateLimiter(
            redis_client=None, default_limit=5, default_window_seconds=10
        )
        for i in range(5):
            allowed, info = limiter.is_allowed("client-1")
            assert allowed is True
            assert info["limit"] == 5
            assert info["remaining"] == 4 - i

    def test_blocks_over_limit(self):
        limiter = SlidingWindowRateLimiter(
            redis_client=None, default_limit=3, default_window_seconds=10
        )
        for _ in range(3):
            allowed, _ = limiter.is_allowed("client-1")
            assert allowed is True

        allowed, info = limiter.is_allowed("client-1")
        assert allowed is False
        assert info["remaining"] == 0
        assert info["reset"] > 0

    def test_isolates_different_keys(self):
        limiter = SlidingWindowRateLimiter(
            redis_client=None, default_limit=2, default_window_seconds=10
        )
        limiter.is_allowed("client-A")
        limiter.is_allowed("client-A")
        allowed_a, _ = limiter.is_allowed("client-A")
        assert allowed_a is False

        allowed_b, _ = limiter.is_allowed("client-B")
        assert allowed_b is True

    def test_window_sliding_expiration(self):
        limiter = SlidingWindowRateLimiter(
            redis_client=None, default_limit=2, default_window_seconds=1
        )
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        assert limiter.is_allowed("client-1")[0] is False

        time.sleep(1.1)
        allowed, info = limiter.is_allowed("client-1")
        assert allowed is True
        assert info["remaining"] == 1


# ---------------------------------------------------------------------------
# Unit tests: Redis sliding window (using fakeredis)
# ---------------------------------------------------------------------------


class TestRedisSlidingWindow:
    @pytest.fixture
    def redis_client(self):
        return fakeredis.FakeRedis(decode_responses=True)

    def test_redis_allows_and_blocks(self, redis_client):
        limiter = SlidingWindowRateLimiter(
            redis_client=redis_client, default_limit=3, default_window_seconds=5
        )
        for i in range(3):
            allowed, info = limiter.is_allowed("redis-client")
            assert allowed is True
            assert info["remaining"] == 2 - i

        allowed, info = limiter.is_allowed("redis-client")
        assert allowed is False
        assert info["remaining"] == 0

    def test_redis_reset(self, redis_client):
        limiter = SlidingWindowRateLimiter(
            redis_client=redis_client, default_limit=2, default_window_seconds=5
        )
        limiter.is_allowed("key-1")
        limiter.is_allowed("key-1")
        assert limiter.is_allowed("key-1")[0] is False

        limiter.reset("key-1")
        assert limiter.is_allowed("key-1")[0] is True


# ---------------------------------------------------------------------------
# Integration tests: RateLimitMiddleware
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareIntegration:
    @pytest.fixture
    def app_with_limiter(self):
        app = FastAPI()
        limiter = SlidingWindowRateLimiter(
            redis_client=None, default_limit=3, default_window_seconds=10
        )
        app.add_middleware(
            RateLimitMiddleware, limiter=limiter, exempt_paths=["/health"]
        )

        @app.get("/health")
        def health():
            return {"status": "ok"}

        @app.get("/test")
        def test_endpoint():
            return {"data": "success"}

        return app

    def test_headers_returned(self, app_with_limiter):
        client = TestClient(app_with_limiter)
        resp = client.get("/test", headers={"X-User-ID": "u1"})
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "3"
        assert resp.headers["X-RateLimit-Remaining"] == "2"

    def test_exceeding_rate_limit_returns_429(self, app_with_limiter):
        client = TestClient(app_with_limiter)
        for _ in range(3):
            resp = client.get("/test", headers={"X-User-ID": "u-rate"})
            assert resp.status_code == 200

        blocked = client.get("/test", headers={"X-User-ID": "u-rate"})
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in blocked.headers
        assert "Rate limit exceeded" in blocked.json()["detail"]

    def test_exempt_paths_not_rate_limited(self, app_with_limiter):
        client = TestClient(app_with_limiter)
        for _ in range(10):
            resp = client.get("/health")
            assert resp.status_code == 200
