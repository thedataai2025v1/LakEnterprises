"""FastAPI route integration tests for Process and Approval APIs with RBAC."""

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.db import reset_db
from lakenterprises.seed import seed_all


@pytest.fixture(autouse=True)
def setup_database():
    reset_db()
    seed_all()
    yield
    reset_db()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def auth_header(client: TestClient, role: str) -> dict[str, str]:
    res = client.post(f"/api/v1/auth/demo/{role}")
    assert res.status_code == 200, f"Demo login failed for {role}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_template_routes_rbac(client):
    analyst_h = auth_header(client, "analyst")
    viewer_h = auth_header(client, "viewer")
    admin_h = auth_header(client, "admin")

    # 1. Viewer cannot create template (403)
    resp = client.post(
        "/api/v1/processes/templates",
        headers=viewer_h,
        json={"name": "Viewer Template"},
    )
    assert resp.status_code == 403

    # 2. Analyst can create template (201)
    resp = client.post(
        "/api/v1/processes/templates",
        headers=analyst_h,
        json={
            "name": "Analyst Workflow Template",
            "description": "Standard review template",
            "definition": {"steps": [{"name": "Step A", "role": "analyst"}]},
        },
    )
    assert resp.status_code == 201
    tpl_id = resp.json()["id"]

    # 3. Viewer can view template (200)
    resp = client.get(f"/api/v1/processes/templates/{tpl_id}", headers=viewer_h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Analyst Workflow Template"

    # 4. Analyst cannot delete template (requires admin) (403)
    resp = client.delete(f"/api/v1/processes/templates/{tpl_id}", headers=analyst_h)
    assert resp.status_code == 403

    # 5. Admin can delete template (204)
    resp = client.delete(f"/api/v1/processes/templates/{tpl_id}", headers=admin_h)
    assert resp.status_code == 204


def test_process_instance_and_task_routes(client):
    analyst_h = auth_header(client, "analyst")

    # Create template
    resp = client.post(
        "/api/v1/processes/templates",
        headers=analyst_h,
        json={
            "name": "Multi-Step Process",
            "definition": {
                "steps": [
                    {"name": "Step 1: Extract", "role": "analyst"},
                    {"name": "Step 2: Signoff", "role": "manager"},
                ]
            },
        },
    )
    tpl_id = resp.json()["id"]

    # Start instance
    resp = client.post(
        "/api/v1/processes/instances",
        headers=analyst_h,
        json={"template_id": tpl_id, "title": "Run #1"},
    )
    assert resp.status_code == 201
    inst_data = resp.json()
    inst_id = inst_data["id"]
    assert len(inst_data["tasks"]) == 2
    task1_id = inst_data["tasks"][0]["id"]

    # Update task status: pending -> in_progress
    resp = client.patch(
        f"/api/v1/processes/tasks/{task1_id}",
        headers=analyst_h,
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # Transition instance: active -> paused -> active
    resp = client.post(
        f"/api/v1/processes/instances/{inst_id}/transition",
        headers=analyst_h,
        json={"status": "paused"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    # Illegal transition: paused -> completed (direct completion from paused is not allowed)
    resp = client.post(
        f"/api/v1/processes/instances/{inst_id}/transition",
        headers=analyst_h,
        json={"status": "completed"},
    )
    assert resp.status_code == 400


def test_approval_routes_rbac(client):
    analyst_h = auth_header(client, "analyst")
    manager_h = auth_header(client, "manager")
    viewer_h = auth_header(client, "viewer")

    # 1. Analyst creates approval request
    resp = client.post(
        "/api/v1/approvals",
        headers=analyst_h,
        json={
            "target_type": "process_instance",
            "target_id": "inst-999",
            "action": "sign_off",
        },
    )
    assert resp.status_code == 201
    appr_id = resp.json()["id"]

    # 2. Viewer tries to approve (403)
    resp = client.post(
        f"/api/v1/approvals/{appr_id}/approve",
        headers=viewer_h,
        json={"comment": "LGTM"},
    )
    assert resp.status_code == 403

    # 3. Manager approves (200)
    resp = client.post(
        f"/api/v1/approvals/{appr_id}/approve",
        headers=manager_h,
        json={"comment": "Approved by manager"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["comment"] == "Approved by manager"
