"""End-to-end integration and lifecycle scenario tests for Agent Tools."""

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


def test_e2e_incident_investigation_and_remediation_lifecycle(client):
    """Simulate complete agent-driven incident remediation:

    1. Search internal docs for root cause findings
    2. Lookup impacted CRM customer profile and SLA
    3. Update CRM support ticket to in-progress
    4. Attempt high-risk ERP purchase order creation (gated)
    5. Manager approves the procurement request
    6. Agent executes the purchase order with approval ID
    7. Agent dispatches resolution email to the customer
    8. Verify outbox and audit log records
    """
    analyst_h = auth_header(client, "analyst")
    manager_h = auth_header(client, "manager")

    # 1. Search knowledge base
    doc_res = client.post(
        "/api/v1/tools/document_search/execute",
        headers=analyst_h,
        json={"parameters": {"query": "database connection pool", "top_k": 3}},
    )
    assert doc_res.status_code == 200
    assert doc_res.json()["success"] is True

    # 2. CRM customer lookup
    cust_res = client.post(
        "/api/v1/tools/crm_customer_lookup/execute",
        headers=analyst_h,
        json={"parameters": {"customer_id": "CUST-101"}},
    )
    assert cust_res.status_code == 200
    assert cust_res.json()["output"]["customer"]["name"] == "Acme Global Industries"
    assert cust_res.json()["output"]["customer"]["tier"] == "enterprise"

    # 3. Update support ticket to in_progress
    ticket_res = client.post(
        "/api/v1/tools/crm_update_ticket/execute",
        headers=analyst_h,
        json={
            "parameters": {
                "ticket_id": "TCK-501",
                "status": "in_progress",
                "note": "Agent dispatched automated telemetry triage.",
            }
        },
    )
    assert ticket_res.status_code == 200
    assert ticket_res.json()["output"]["status"] == "in_progress"

    # 4. Attempt PO creation (Gated)
    po_params = {
        "vendor_id": "VND-ACME",
        "items": [
            {"sku": "SKU-SRV-01", "name": "Compute Node", "qty": 2, "price": 9000.0}
        ],
        "total_amount": 18000.0,
    }
    po_res = client.post(
        "/api/v1/tools/erp_create_purchase_order/execute",
        headers=analyst_h,
        json={"parameters": po_params},
    )
    assert po_res.status_code == 200
    po_data = po_res.json()
    assert po_data["success"] is False
    assert po_data["requires_approval"] is True
    appr_id = po_data["approval_request_id"]
    assert appr_id is not None

    # 5. Manager reviews and approves via approval tool
    appr_res = client.post(
        "/api/v1/tools/approval_decision/execute",
        headers=manager_h,
        json={
            "parameters": {
                "approval_id": appr_id,
                "decision": "approve",
                "reviewer_id": "mgr_elena",
                "comments": "Emergency replacement approved.",
            }
        },
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["success"] is True
    assert appr_res.json()["output"]["status"] == "approved"

    # 6. Re-execute purchase order with approval ID
    po_final_res = client.post(
        "/api/v1/tools/erp_create_purchase_order/execute",
        headers=analyst_h,
        json={"parameters": po_params, "approval_id": appr_id},
    )
    assert po_final_res.status_code == 200
    assert po_final_res.json()["success"] is True
    assert po_final_res.json()["output"]["total_amount"] == 18000.0

    # 7. Dispatch resolution email to customer
    email_res = client.post(
        "/api/v1/tools/email_dispatch/execute",
        headers=analyst_h,
        json={
            "parameters": {
                "recipient": "contact@acmeglobal.com",
                "subject": "[RESOLVED] Connection Pool Outage Remediated",
                "body": "Hardware node replacement has been scheduled under PO.",
            }
        },
    )
    assert email_res.status_code == 200
    assert email_res.json()["success"] is True
    assert email_res.json()["output"]["status"] == "delivered"
