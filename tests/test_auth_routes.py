"""Integration tests for FastAPI authentication routes."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.db import get_db_session, init_db, reset_db
from lakenterprises.seed import seed_all


@pytest.fixture(scope="module")
def test_app():
    temp_db = tempfile.mktemp(suffix=".db")
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
    init_db()
    seed_all()
    app = create_app()
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestDemoTokens:
    def test_get_demo_tokens_all(self, client):
        resp = client.get("/api/v1/auth/demo-tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert "viewer" in data
        assert "analyst" in data
        assert "admin" in data
        assert data["token_type"] == "bearer"

    def test_post_demo_role_viewer(self, client):
        resp = client.post("/api/v1/auth/demo/viewer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["roles"] == ["viewer"]
        assert "read_document" in data["user"]["permissions"]

    def test_post_demo_role_analyst(self, client):
        resp = client.post("/api/v1/auth/demo/analyst")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["roles"] == ["analyst"]
        assert "create_session" in data["user"]["permissions"]

    def test_post_demo_role_admin(self, client):
        resp = client.post("/api/v1/auth/demo/admin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["roles"] == ["admin"]
        assert "user_management" in data["user"]["permissions"]

    def test_post_demo_role_invalid(self, client):
        resp = client.post("/api/v1/auth/demo/invalid_role")
        assert resp.status_code == 400
        assert "Invalid demo role" in resp.json()["detail"]


class TestAuthLoginAndMe:
    def test_login_success(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": "Admin123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "admin"

    def test_login_failure_bad_password(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        assert "Invalid username or password" in resp.json()["detail"]

    def test_get_me_authenticated(self, client):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": "Admin123!"},
        )
        token = login_resp.json()["access_token"]

        me_resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200
        profile = me_resp.json()
        assert profile["username"] == "admin"
        assert "admin" in profile["roles"]
        assert profile["is_authenticated"] is True

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestRefreshAndLogout:
    def test_refresh_token_flow(self, client):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": "Admin123!"},
        )
        refresh_tok = login_resp.json()["refresh_token"]

        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_tok},
        )
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data

    def test_logout_revokes_token(self, client):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": "Admin123!"},
        )
        access_tok = login_resp.json()["access_token"]

        # Logout
        logout_resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        assert logout_resp.status_code == 200
        assert "Logged out successfully" in logout_resp.json()["detail"]

        # Accessing /me after logout fails
        me_resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_tok}"}
        )
        assert me_resp.status_code == 401
