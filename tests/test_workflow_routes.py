"""Integration tests for Phase 10 FastAPI workflow REST endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lakenterprises.app import create_app
from lakenterprises.auth.service import AuthService


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    service = AuthService(secret_key="test-secret-key-lakenterprises-jwt")
    token = service.create_access_token(
        user_id="workflow_tester",
        extra_claims={"roles": ["analyst", "admin"]},
    )
    return {"Authorization": f"Bearer {token}"}


def test_workflow_run_endpoint(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "title": "API Workflow Investigation",
        "instruction": "Analyze invoice mismatch and review compliance standards",
        "context": {"amount": 7500.0, "vendor": "Acme Corp"},
    }
    response = client.post(
        "/api/v1/workflow/run",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "process_id" in data
    assert data["title"] == "API Workflow Investigation"
    assert data["current_status"] in ["COMPLETED", "ESCALATED"]
    assert "orchestrator" in data["routing_history"]


def test_workflow_get_state_and_checkpoints(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. Run a workflow first
    payload = {
        "title": "Query State Workflow",
        "instruction": "Verify contract clauses",
        "context": {"amount": 1000.0},
    }
    run_resp = client.post("/api/v1/workflow/run", json=payload, headers=auth_headers)
    assert run_resp.status_code == 200
    proc_id = run_resp.json()["process_id"]

    # 2. Get state
    state_resp = client.get(f"/api/v1/workflow/{proc_id}/state", headers=auth_headers)
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["process_id"] == proc_id

    # 3. Get checkpoints
    cp_resp = client.get(
        f"/api/v1/workflow/{proc_id}/checkpoints", headers=auth_headers
    )
    assert cp_resp.status_code == 200
    checkpoints = cp_resp.json()
    assert len(checkpoints) >= 1

    # 4. Get events
    ev_resp = client.get(f"/api/v1/workflow/{proc_id}/events", headers=auth_headers)
    assert ev_resp.status_code == 200
    events = ev_resp.json()
    assert len(events) >= 1


def test_workflow_resume_endpoint(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. Run initial
    run_resp = client.post(
        "/api/v1/workflow/run",
        json={"title": "Pause-Resume Test", "instruction": "Initial run"},
        headers=auth_headers,
    )
    proc_id = run_resp.json()["process_id"]

    # 2. Resume
    resume_resp = client.post(
        f"/api/v1/workflow/{proc_id}/resume",
        json={"resume_inputs": {"supervisor_override": True}},
        headers=auth_headers,
    )
    assert resume_resp.status_code == 200
    resumed_data = resume_resp.json()
    assert resumed_data["context"].get("supervisor_override") is True


def test_workflow_state_not_found(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/workflow/non-existent-id/state", headers=auth_headers)
    assert resp.status_code == 404
