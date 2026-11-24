"""End-to-End integration tests for Identity, Access Control, and Protected Routes."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.db import get_db_session, init_db, reset_db
from lakenterprises.seed import seed_all


@pytest.fixture(scope="module")
def app_instance():
    temp_db = tempfile.mktemp(suffix=".db")
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
    init_db()
    seed_all()
    return create_app()


@pytest.fixture
def client(app_instance):
    return TestClient(app_instance)


@pytest.fixture
def tokens(client):
    resp = client.get("/api/v1/auth/demo-tokens")
    assert resp.status_code == 200
    return resp.json()


class TestHealthEndpointsE2E:
    def test_health_live(self, client):
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "X-Request-ID" in resp.headers

    def test_health_ready(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"


class TestRBACProtectedRoutesE2E:
    def test_unauthenticated_request_rejected(self, client):
        resp = client.get("/api/v1/protected/user")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    def test_viewer_access(self, client, tokens):
        viewer_tok = tokens["viewer"]
        headers = {"Authorization": f"Bearer {viewer_tok}"}

        # Viewer can access general authenticated user endpoint
        user_resp = client.get("/api/v1/protected/user", headers=headers)
        assert user_resp.status_code == 200

        # Viewer CANNOT access analyst endpoint (403)
        analyst_resp = client.get("/api/v1/protected/analyst", headers=headers)
        assert analyst_resp.status_code == 403

        # Viewer CANNOT access admin endpoint (403)
        admin_resp = client.get("/api/v1/protected/admin", headers=headers)
        assert admin_resp.status_code == 403

    def test_analyst_access(self, client, tokens):
        analyst_tok = tokens["analyst"]
        headers = {"Authorization": f"Bearer {analyst_tok}"}

        # Analyst CAN access user and analyst endpoints
        assert client.get("/api/v1/protected/user", headers=headers).status_code == 200
        assert (
            client.get("/api/v1/protected/analyst", headers=headers).status_code == 200
        )

        # Analyst CANNOT access admin endpoint (403)
        admin_resp = client.get("/api/v1/protected/admin", headers=headers)
        assert admin_resp.status_code == 403

    def test_admin_access(self, client, tokens):
        admin_tok = tokens["admin"]
        headers = {"Authorization": f"Bearer {admin_tok}"}

        # Admin CAN access all endpoints
        assert client.get("/api/v1/protected/user", headers=headers).status_code == 200
        assert (
            client.get("/api/v1/protected/analyst", headers=headers).status_code == 200
        )
        assert client.get("/api/v1/protected/admin", headers=headers).status_code == 200

    def test_headers_and_audit_present_on_protected_calls(self, client, tokens):
        headers = {"Authorization": f"Bearer {tokens['admin']}"}
        resp = client.get("/api/v1/protected/admin", headers=headers)
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
