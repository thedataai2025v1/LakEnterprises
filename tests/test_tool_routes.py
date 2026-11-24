"""FastAPI route integration tests for Agent Tools API (/api/v1/tools)."""

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


def test_list_tools_endpoint(client):
    analyst_h = auth_header(client, "analyst")
    resp = client.get("/api/v1/tools", headers=analyst_h)
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) >= 10
    tool_names = [t["name"] for t in tools]
    assert "crm_customer_lookup" in tool_names
    assert "erp_create_purchase_order" in tool_names


def test_list_tools_filtering(client):
    analyst_h = auth_header(client, "analyst")
    resp_read = client.get("/api/v1/tools?category=read", headers=analyst_h)
    assert resp_read.status_code == 200
    for t in resp_read.json():
        assert t["category"] == "read"

    resp_risk = client.get("/api/v1/tools?risk_level=high", headers=analyst_h)
    assert resp_risk.status_code == 200
    for t in resp_risk.json():
        assert t["risk_level"] == "high"


def test_get_tool_schemas_endpoint(client):
    analyst_h = auth_header(client, "analyst")
    resp = client.get("/api/v1/tools/schemas", headers=analyst_h)
    assert resp.status_code == 200
    schemas = resp.json()
    assert len(schemas) >= 10
    assert all("type" in s and "function" in s for s in schemas)


def test_get_tool_by_name(client):
    analyst_h = auth_header(client, "analyst")
    resp = client.get("/api/v1/tools/crm_customer_lookup", headers=analyst_h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "crm_customer_lookup"
    assert "customer_id" in data["parameters_schema"]["properties"]

    resp_404 = client.get("/api/v1/tools/nonexistent_tool", headers=analyst_h)
    assert resp_404.status_code == 404


def test_execute_read_only_tool_as_viewer(client):
    viewer_h = auth_header(client, "viewer")
    resp = client.post(
        "/api/v1/tools/crm_customer_lookup/execute",
        headers=viewer_h,
        json={"parameters": {"customer_id": "CUST-101"}},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    assert res["output"]["found"] is True
    assert res["output"]["customer"]["name"] == "Acme Global Industries"


def test_execute_write_tool_as_viewer_forbidden(client):
    viewer_h = auth_header(client, "viewer")
    resp = client.post(
        "/api/v1/tools/crm_update_ticket/execute",
        headers=viewer_h,
        json={"parameters": {"ticket_id": "TCK-501", "status": "resolved"}},
    )
    assert resp.status_code == 403


def test_execute_approval_gated_workflow(client):
    analyst_h = auth_header(client, "analyst")
    manager_h = auth_header(client, "manager")

    # 1. Analyst attempts execution -> triggers approval request
    po_params = {
        "vendor_id": "VND-ACME",
        "items": [{"sku": "SKU-SRV-01", "qty": 1, "price": 9000.0}],
        "total_amount": 9000.0,
    }
    resp1 = client.post(
        "/api/v1/tools/erp_create_purchase_order/execute",
        headers=analyst_h,
        json={"parameters": po_params},
    )
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["success"] is False
    assert res1["requires_approval"] is True
    assert res1["approval_request_id"] is not None
    appr_id = res1["approval_request_id"]

    # 2. Manager approves the request via /api/v1/approvals
    resp_approve = client.post(
        f"/api/v1/approvals/{appr_id}/approve",
        headers=manager_h,
        json={"comments": "Budget approved for node."},
    )
    assert resp_approve.status_code == 200

    # 3. Analyst executes again with the approval_id -> success!
    resp2 = client.post(
        "/api/v1/tools/erp_create_purchase_order/execute",
        headers=analyst_h,
        json={"parameters": po_params, "approval_id": appr_id},
    )
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["success"] is True
    assert res2["output"]["order_id"].startswith("PO-")
    assert res2["output"]["total_amount"] == 9000.0
