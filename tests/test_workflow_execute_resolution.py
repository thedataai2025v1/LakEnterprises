"""Unit tests for Phase 11 resolution execution via shared tool path (P11-4)."""

from __future__ import annotations

from lakenterprises.workflow.nodes_resolution import execute_resolution_node
from lakenterprises.workflow.state import create_initial_workflow_state


def test_execute_resolution_node_crm_ticket() -> None:
    state = create_initial_workflow_state(
        process_id="proc-res-01",
        title="Resolution Execution Test",
        instruction="Investigate billing discrepancy",
        initial_context={"ticket_id": "TCK-5544"},
    )
    state["final_outcome"] = "Refund approved and credited to customer account."

    result = execute_resolution_node(state)

    assert result["active_node"] == "execute_resolution"
    assert "execute_resolution" in result["routing_history"]
    assert "resolution_execution" in result
    assert result["resolution_execution"]["tool_name"] == "crm_update_ticket"
    assert result["resolution_execution"]["ticket_id"] == "TCK-5544"
    assert result["resolution_execution"]["status"] == "executed"
    assert "crm_update_ticket" in result["action_results"]
    assert any(
        "Executed tool 'crm_update_ticket'" in h.get("details", "")
        for h in result["history"]
    )
