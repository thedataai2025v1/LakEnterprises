"""Unit tests for Phase 10 workflow graph execution nodes."""

from __future__ import annotations

from lakenterprises.workflow.nodes_investigate import (
    document_analyst_node,
    knowledge_retriever_node,
)
from lakenterprises.workflow.nodes_orchestrator import (
    orchestrator_node,
    route_orchestrator,
)
from lakenterprises.workflow.nodes_resolution import (
    compliance_node,
    escalation_node,
    finalize_node,
    response_draft_node,
)
from lakenterprises.workflow.state import create_initial_workflow_state


def test_orchestrator_node_and_routing() -> None:
    state = create_initial_workflow_state(
        "proc-orch-1",
        "Orchestration Test",
        "Review invoice anomaly and check compliance guidelines",
    )
    result = orchestrator_node(state)
    assert result["active_node"] == "orchestrator"
    assert "orchestrator" in result["routing_history"]
    assert "supervisor" in result["agent_outputs"]
    assert result["current_status"] == "IN_PROGRESS"

    # Test conditional routing decision
    next_node = route_orchestrator(result)
    assert next_node in [
        "document_analyst",
        "compliance",
        "knowledge_retriever",
        "response_draft",
        "escalation",
        "finalize",
    ]


def test_document_analyst_node() -> None:
    state = create_initial_workflow_state(
        "proc-doc-1",
        "Document Node Test",
        "Analyze contract dispute details",
    )
    result = document_analyst_node(state)
    assert result["active_node"] == "document_analyst"
    assert "document_analyst" in result["routing_history"]
    assert "document_analyst" in result["agent_outputs"]
    assert len(result["collected_documents"]) >= 1


def test_knowledge_retriever_node() -> None:
    state = create_initial_workflow_state(
        "proc-kr-1",
        "Knowledge Node Test",
        "Search compliance policies regarding transaction reversals",
    )
    result = knowledge_retriever_node(state)
    assert result["active_node"] == "knowledge_retriever"
    assert "knowledge_retriever" in result["routing_history"]
    assert "knowledge_retriever" in result["agent_outputs"]
    assert len(result["citations"]) >= 1


def test_compliance_node_under_limit() -> None:
    state = create_initial_workflow_state(
        "proc-comp-1",
        "Compliance Standard Test",
        "Review transaction",
        initial_context={"amount": 4000.0},
    )
    result = compliance_node(state)
    assert result["active_node"] == "compliance"
    assert "compliance" in result["routing_history"]
    assert "compliance" in result["agent_outputs"]
    assert result["agent_outputs"]["compliance"]["is_compliant"] is True
    assert result["human_intervention_required"] is False


def test_compliance_node_over_limit_triggers_escalation_flag() -> None:
    state = create_initial_workflow_state(
        "proc-comp-2",
        "Compliance High Value Test",
        "Review large transaction",
        initial_context={"amount": 150000.0},
    )
    result = compliance_node(state)
    assert result["active_node"] == "compliance"
    assert result["human_intervention_required"] is True
    assert result["agent_outputs"]["compliance"]["is_compliant"] is False


def test_escalation_node() -> None:
    state = create_initial_workflow_state(
        "proc-esc-1",
        "Escalation Test",
        "Escalate transaction anomaly to compliance officer",
        initial_context={"severity": "CRITICAL"},
    )
    result = escalation_node(state)
    assert result["active_node"] == "escalation"
    assert "escalation" in result["routing_history"]
    assert result["current_status"] == "ESCALATED"
    assert result["human_intervention_required"] is True
    assert "escalation_handoff" in result["agent_outputs"]


def test_response_draft_node() -> None:
    state = create_initial_workflow_state(
        "proc-draft-1",
        "Draft Test",
        "Synthesize investigation findings for customer",
    )
    result = response_draft_node(state)
    assert result["active_node"] == "response_draft"
    assert "response_draft" in result["routing_history"]
    assert "response_drafter" in result["agent_outputs"]


def test_finalize_node() -> None:
    state = create_initial_workflow_state(
        "proc-fin-1",
        "Finalize Test",
        "Complete enterprise workflow",
    )
    result = finalize_node(state)
    assert result["active_node"] == "finalize"
    assert result["current_status"] == "COMPLETED"
    assert result["final_outcome"] is not None
    assert "completed" in result["final_outcome"].lower()
