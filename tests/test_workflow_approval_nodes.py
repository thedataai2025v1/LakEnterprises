"""Unit tests for Phase 11 human approval interrupt node and decision routing (P11-1)."""

from __future__ import annotations

from lakenterprises.workflow.nodes_approval import (
    human_approval_node,
    route_after_approval,
    route_after_escalation,
)
from lakenterprises.workflow.state import create_initial_workflow_state


def test_human_approval_node_pending_pause() -> None:
    state = create_initial_workflow_state(
        process_id="proc-appr-01",
        title="High Value Purchase",
        instruction="Purchase hardware licenses",
        initial_context={"amount": 125000.0, "severity": "CRITICAL"},
    )
    result = human_approval_node(state)

    assert result["active_node"] == "human_approval"
    assert "human_approval" in result["routing_history"]
    assert result["approval_required"] is True
    assert result["approval_status"] == "pending"
    assert result["current_status"] == "AWAITING_APPROVAL"
    assert result["escalation_tier"] == "tier_4_executive"
    assert result["target_role"] == "admin"
    assert result["sla_hours"] == 1.0
    assert result["approval_request_id"] is not None


def test_human_approval_node_approved_resumption() -> None:
    state = create_initial_workflow_state(
        process_id="proc-appr-02",
        title="Approved Purchase",
        instruction="Purchase hardware licenses",
    )
    state["approval_decision"] = {
        "status": "approved",
        "reviewed_by": "CFO Jane Doe",
        "comment": "Approved per budget.",
    }
    result = human_approval_node(state)

    assert result["active_node"] == "human_approval"
    assert result["approval_status"] == "approved"
    assert result["current_status"] == "IN_PROGRESS"
    assert result["approval_required"] is False
    assert any(
        "Approved by CFO Jane Doe" in h.get("details", "") for h in result["history"]
    )


def test_human_approval_node_rejected() -> None:
    state = create_initial_workflow_state(
        process_id="proc-appr-03",
        title="Rejected Purchase",
        instruction="Purchase hardware licenses",
    )
    state["approval_decision"] = {
        "status": "rejected",
        "reviewed_by": "Auditor Smith",
        "comment": "Exceeds fiscal limits.",
    }
    result = human_approval_node(state)

    assert result["active_node"] == "human_approval"
    assert result["approval_status"] == "rejected"
    assert result["current_status"] == "REJECTED"


def test_routing_after_escalation_and_approval() -> None:
    # 1. Route after escalation with approval required
    state_pending = create_initial_workflow_state(
        process_id="proc-route-01",
        title="Route Test",
        instruction="Check routing",
    )
    state_pending["approval_required"] = True
    state_pending["approval_status"] = "pending"
    assert route_after_escalation(state_pending) == "human_approval"

    # 2. Route after escalation without approval required
    state_no_appr = create_initial_workflow_state(
        process_id="proc-route-02",
        title="Route Test 2",
        instruction="Check routing 2",
    )
    state_no_appr["approval_required"] = False
    assert route_after_escalation(state_no_appr) == "execute_resolution"

    # 3. Route after approval: approved -> execute_resolution
    state_approved = dict(state_pending)
    state_approved["approval_status"] = "approved"
    assert route_after_approval(state_approved) == "execute_resolution"

    # 4. Route after approval: rejected -> finalize
    state_rejected = dict(state_pending)
    state_rejected["approval_status"] = "rejected"
    assert route_after_approval(state_rejected) == "finalize"
