"""Unit and integration tests for approval-gated write tools and ToolExecutor."""

import pytest

from lakenterprises.db import get_db_session, init_db, reset_db
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.audit import AuditService
from lakenterprises.tools.executor import ToolExecutor
from lakenterprises.tools.registry import ToolRegistry
from lakenterprises.tools.write_tools import (ApprovalDecisionTool,
                                              CRMUpdateTicketTool,
                                              EmailDispatchTool,
                                              ERPCreatePurchaseOrderTool,
                                              ProcessTaskSubmitTool)


@pytest.fixture
def write_tools_env(tmp_path, monkeypatch):
    db_file = tmp_path / "test_write_tools.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    reset_db()
    init_db()

    session = get_db_session()
    reg = ToolRegistry()
    appr_svc = ApprovalService(session)
    audit_svc = AuditService(session)

    # Register write tools
    reg.register(CRMUpdateTicketTool())
    reg.register(ERPCreatePurchaseOrderTool())
    reg.register(EmailDispatchTool())
    reg.register(ProcessTaskSubmitTool())
    reg.register(ApprovalDecisionTool(appr_svc))

    executor = ToolExecutor(
        registry=reg,
        approval_service=appr_svc,
        audit_service=audit_svc,
    )

    yield executor, appr_svc, audit_svc, session
    session.close()


def test_crm_update_ticket_tool(write_tools_env):
    executor, _, _, _ = write_tools_env
    res = executor.execute(
        tool_name="crm_update_ticket",
        parameters={
            "ticket_id": "TCK-501",
            "status": "in_progress",
            "note": "Investigating node metrics.",
        },
        user_roles=["analyst"],
    )
    assert res.success is True
    assert res.output["status"] == "in_progress"
    assert "Investigating node metrics." in res.output["notes"]


def test_email_dispatch_tool(write_tools_env):
    executor, _, _, _ = write_tools_env
    res = executor.execute(
        tool_name="email_dispatch",
        parameters={
            "recipient": "customer@acme.com",
            "subject": "Incident Notification",
            "body": "Your ticket TCK-501 is being investigated.",
        },
        user_roles=["analyst"],
    )
    assert res.success is True
    assert res.output["status"] == "delivered"
    assert res.output["to"] == "customer@acme.com"


def test_erp_create_purchase_order_gating_and_approval(write_tools_env):
    executor, appr_svc, _, _ = write_tools_env

    # 1. Analyst attempts execution without approval -> Auto-creates approval request
    po_params = {
        "vendor_id": "VND-ACME",
        "items": [{"sku": "SKU-SRV-01", "qty": 3, "price": 9000.0}],
        "total_amount": 27000.0,
    }
    res_gated = executor.execute(
        tool_name="erp_create_purchase_order",
        parameters=po_params,
        user_roles=["analyst"],
        user_id="analyst_dev",
    )
    assert res_gated.success is False
    assert res_gated.requires_approval is True
    assert res_gated.approval_request_id is not None
    appr_id = res_gated.approval_request_id

    # 2. Manager approves the request using approval_decision tool
    res_approve = executor.execute(
        tool_name="approval_decision",
        parameters={
            "approval_id": appr_id,
            "decision": "approve",
            "reviewer_id": "mgr_carol",
            "comments": "Approved hardware replacement.",
        },
        user_roles=["manager"],
    )
    assert res_approve.success is True
    assert res_approve.output["status"] == "approved"

    # 3. Analyst re-runs with approved request ID -> succeeds
    res_success = executor.execute(
        tool_name="erp_create_purchase_order",
        parameters=po_params,
        user_roles=["analyst"],
        user_id="analyst_dev",
        approval_id=appr_id,
    )
    assert res_success.success is True
    assert res_success.output["order_id"].startswith("PO-")
    assert res_success.output["total_amount"] == 27000.0


def test_approval_decision_invalid_action(write_tools_env):
    executor, appr_svc, _, _ = write_tools_env
    req = appr_svc.request_approval("t", "i", "a", "u")

    res = executor.execute(
        tool_name="approval_decision",
        parameters={
            "approval_id": req.id,
            "decision": "invalid_choice",
            "reviewer_id": "mgr",
        },
        user_roles=["manager"],
    )
    assert res.success is False
    assert "Must be 'approve' or 'reject'" in res.error
