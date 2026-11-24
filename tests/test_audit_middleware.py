"""Tests for AuditMiddleware and Request-ID propagation."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lakenterprises.auth.audit_middleware import AuditMiddleware
from lakenterprises.services.audit import AuditService


class TestAuditMiddleware:
    @pytest.fixture
    def audit_service(self):
        return AuditService(db_session=None)

    @pytest.fixture
    def test_client(self, audit_service):
        app = FastAPI()
        app.add_middleware(AuditMiddleware, audit_service=audit_service)

        @app.get("/api/v1/ping")
        def ping():
            return {"ping": "pong"}

        @app.get("/api/v1/error")
        def error_endpoint():
            raise HTTPException(status_code=400, detail="Custom bad request")

        return TestClient(app)

    def test_generates_request_id_when_missing(self, test_client):
        resp = test_client.get("/api/v1/ping")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 10

    def test_preserves_client_request_id(self, test_client):
        custom_id = "client-trace-12345"
        resp = test_client.get("/api/v1/ping", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == custom_id

    def test_records_successful_audit_entry(self, test_client, audit_service):
        resp = test_client.get("/api/v1/ping")
        assert resp.status_code == 200

        logs = audit_service.get_logs(action="HTTP_REQUEST")
        assert len(logs) >= 1
        entry = logs[0]
        assert entry["action"] == "HTTP_REQUEST"
        assert entry["details"]["path"] == "/api/v1/ping"
        assert entry["details"]["method"] == "GET"
        assert entry["details"]["status_code"] == 200
        assert entry["severity"] == "INFO"
        assert "duration_ms" in entry["details"]

    def test_records_client_error_audit_entry(self, test_client, audit_service):
        resp = test_client.get("/api/v1/error")
        assert resp.status_code == 400

        logs = audit_service.get_logs(action="HTTP_REQUEST")
        error_entries = [e for e in logs if e["details"].get("status_code") == 400]
        assert len(error_entries) >= 1
        assert error_entries[0]["severity"] == "WARNING"
