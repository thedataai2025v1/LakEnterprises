"""Tests for PIIScrubberMiddleware integration."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lakenterprises.guardrails.middleware import PIIScrubberMiddleware


def test_middleware_allows_safe_requests():
    app = FastAPI()
    app.add_middleware(PIIScrubberMiddleware, block_on_secret=True)

    @app.get("/api/v1/ping")
    def ping():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/api/v1/ping?query=safe_data")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_middleware_blocks_secret_in_query_when_enabled():
    app = FastAPI()
    app.add_middleware(PIIScrubberMiddleware, block_on_secret=True)

    @app.get("/api/v1/secure")
    def secure_endpoint():
        return {"message": "granted"}

    client = TestClient(app)
    malicious_query = "/api/v1/secure?token=AKIAIOSFODNN7EXAMPLE"
    resp = client.get(malicious_query)
    assert resp.status_code == 400
    assert "plaintext credentials" in resp.json()["detail"].lower()


def test_middleware_exempt_paths():
    app = FastAPI()
    app.add_middleware(
        PIIScrubberMiddleware, block_on_secret=True, exempt_paths=["/health"]
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/health?key=AKIAIOSFODNN7EXAMPLE")
    assert resp.status_code == 200
