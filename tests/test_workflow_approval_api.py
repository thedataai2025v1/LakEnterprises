"""Integration tests for Phase 11 approval decide and resume API endpoints (P11-2)."""

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
        user_id="approval_admin",
        extra_claims={"roles": ["admin", "manager"]},
    )
    return {"Authorization": f"Bearer {token}"}


def test_workflow_decide_and_resume_approval(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. Trigger high-value workflow that pauses at human approval
    payload = {
        "title": "High Value Wire Verification",
        "instruction": "Review high value vendor wire of $150,000",
        "input_payload": {"amount": 150000.0, "severity": "CRITICAL"},
    }
    run_resp = client.post("/api/v1/workflow/run", json=payload, headers=auth_headers)
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    proc_id = run_data["process_id"]
    assert run_data["current_status"] in ["AWAITING_APPROVAL", "pending", "in_progress"]
    assert run_data.get("approval_required") is True

    # 2. Query SLA endpoint
    sla_resp = client.get(f"/api/v1/workflow/{proc_id}/sla", headers=auth_headers)
    assert sla_resp.status_code == 200
    sla_data = sla_resp.json()
    assert sla_data["tier"] == "tier_4_executive"
    assert sla_data["target_role"] == "admin"
    assert sla_data["sla_hours"] == 1.0

    # 3. Submit Approval Decision via /decide endpoint
    decide_resp = client.post(
        f"/api/v1/workflow/{proc_id}/decide",
        json={
            "decision": "approved",
            "reviewed_by": "CFO Marcus",
            "comment": "Authorized wire after board check.",
        },
        headers=auth_headers,
    )
    assert decide_resp.status_code == 200
    resumed_data = decide_resp.json()
    assert resumed_data["current_status"] == "COMPLETED"
    assert "execute_resolution" in resumed_data["routing_history"]
    assert resumed_data["approval_decision"]["status"] == "approved"
    assert resumed_data["resolution_execution"]["status"] == "executed"


def test_workflow_decide_rejection(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. Trigger workflow
    payload = {
        "title": "Suspicious Transaction Check",
        "instruction": "Check suspicious debit of $200,000",
        "input_payload": {"amount": 200000.0, "severity": "CRITICAL"},
    }
    run_resp = client.post("/api/v1/workflow/run", json=payload, headers=auth_headers)
    proc_id = run_resp.json()["process_id"]

    # 2. Reject decision
    decide_resp = client.post(
        f"/api/v1/workflow/{proc_id}/decide",
        json={
            "decision": "rejected",
            "reviewed_by": "Risk Officer David",
            "comment": "Denied due to suspicious recipient account.",
        },
        headers=auth_headers,
    )
    assert decide_resp.status_code == 200
    rejected_data = decide_resp.json()
    assert rejected_data["current_status"] == "REJECTED"
    assert rejected_data["status"] == "rejected"
    assert rejected_data["approval_status"] == "rejected"


def test_workflow_decide_invalid_input(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/workflow/dummy-proc/decide",
        json={"decision": "maybe_later"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
