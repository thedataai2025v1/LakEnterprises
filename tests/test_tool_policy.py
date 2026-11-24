"""Unit tests for ToolPolicyEngine and security governance."""

import pytest

from lakenterprises.db import get_db_session, init_db, reset_db
from lakenterprises.services.approval import ApprovalService
from lakenterprises.services.audit import AuditService
from lakenterprises.tools.base import BaseTool, RiskLevel, ToolCategory
from lakenterprises.tools.policy import ToolPolicyEngine
from lakenterprises.tools.registry import ToolRegistry


class SafeReadTool(BaseTool):
    name = "safe_read"
    description = "Safe low risk read tool."
    category = ToolCategory.READ
    risk_level = RiskLevel.LOW
    requires_approval = False
    allowed_roles = ["viewer", "analyst", "manager", "admin"]

    def run(self):
        return "ok"


class HighWriteTool(BaseTool):
    name = "high_write"
    description = "High risk write tool requiring approval."
    category = ToolCategory.WRITE
    risk_level = RiskLevel.HIGH
    requires_approval = True
    allowed_roles = ["analyst", "manager", "admin"]

    def run(self):
        return "written"


@pytest.fixture
def policy_setup(tmp_path, monkeypatch):
    db_file = tmp_path / "test_policy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    reset_db()
    init_db()

    session = get_db_session()
    reg = ToolRegistry()
    reg.register(SafeReadTool())
    reg.register(HighWriteTool())

    appr_svc = ApprovalService(session)
    audit_svc = AuditService(session)
    engine = ToolPolicyEngine(
        registry=reg, approval_service=appr_svc, audit_service=audit_svc
    )
    yield engine, appr_svc, audit_svc, session
    session.close()


def test_policy_unregistered_tool(policy_setup):
    engine, _, _, _ = policy_setup
    decision = engine.evaluate(tool_name="unknown_tool", user_roles=["admin"])
    assert not decision.allowed
    assert "not registered" in decision.reason


def test_policy_role_disallowed(policy_setup):
    engine, _, _, _ = policy_setup
    decision = engine.evaluate(tool_name="high_write", user_roles=["viewer"])
    assert not decision.allowed
    assert (
        "not authorized" in decision.reason.lower()
        or "restricted" in decision.reason.lower()
    )


def test_policy_viewer_safe_read_allowed(policy_setup):
    engine, _, _, _ = policy_setup
    decision = engine.evaluate(tool_name="safe_read", user_roles=["viewer"])
    assert decision.allowed
    assert not decision.requires_approval


def test_policy_analyst_high_write_requires_approval(policy_setup):
    engine, _, _, _ = policy_setup
    decision = engine.evaluate(tool_name="high_write", user_roles=["analyst"])
    assert not decision.allowed
    assert decision.requires_approval
    assert "approval" in decision.reason.lower()


def test_policy_approval_workflow(policy_setup):
    engine, appr_svc, _, _ = policy_setup

    # 1. Create approval request
    req = appr_svc.request_approval(
        target_type="tool",
        target_id="high_write",
        action="execute_tool",
        requested_by_id="analyst_bob",
    )
    req_id = req.id

    # 2. Check pending approval
    decision = engine.evaluate(
        tool_name="high_write",
        user_roles=["analyst"],
        approval_id=req_id,
    )
    assert not decision.allowed
    assert decision.requires_approval
    assert "pending" in decision.reason.lower()

    # 3. Reject approval
    appr_svc.reject(
        request_id=req_id, reviewed_by_id="mgr_alice", comment="Denied due to risk"
    )
    decision_rejected = engine.evaluate(
        tool_name="high_write",
        user_roles=["analyst"],
        approval_id=req_id,
    )
    assert not decision_rejected.allowed
    assert "rejected" in decision_rejected.reason.lower()

    # 4. Create new request and approve it
    req2 = appr_svc.request_approval(
        target_type="tool",
        target_id="high_write",
        action="execute_tool",
        requested_by_id="analyst_bob",
    )
    appr_svc.approve(
        request_id=req2.id, reviewed_by_id="mgr_alice", comment="Approved budget"
    )

    decision_approved = engine.evaluate(
        tool_name="high_write",
        user_roles=["analyst"],
        approval_id=req2.id,
    )
    assert decision_approved.allowed
    assert decision_approved.requires_approval
    assert decision_approved.approval_status == "approved"
