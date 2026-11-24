"""Unit tests for Phase 10 LangGraph workflow graph compilation and WorkflowEngine."""

from __future__ import annotations

import pytest

from lakenterprises.workflow.graph import (
    WorkflowEngine,
    build_enterprise_workflow_graph,
)
from lakenterprises.workflow.state import ProcessStateCheckpointer


def test_build_enterprise_workflow_graph() -> None:
    checkpointer = ProcessStateCheckpointer()
    graph = build_enterprise_workflow_graph(checkpointer=checkpointer)
    assert graph is not None
    # CompiledStateGraph should have nodes registered
    node_keys = list(graph.nodes.keys())
    assert "orchestrator" in node_keys
    assert "document_analyst" in node_keys
    assert "compliance" in node_keys
    assert "knowledge_retriever" in node_keys
    assert "response_drafter" in node_keys
    assert "escalation" in node_keys
    assert "finalize" in node_keys


def test_workflow_engine_run_standard_process() -> None:
    engine = WorkflowEngine()
    final_state = engine.run(
        process_id="proc-eng-100",
        title="Automated Expense Audit",
        instruction="Verify routine travel expense report",
        initial_context={"amount": 450.0},
    )

    assert final_state["process_id"] == "proc-eng-100"
    assert final_state["current_status"] in ["COMPLETED", "ESCALATED"]
    assert len(final_state["routing_history"]) >= 2
    assert "orchestrator" in final_state["routing_history"]

    # Verify checkpointer saved snapshots
    checkpoints = engine.checkpointer.list_checkpoints("proc-eng-100")
    assert len(checkpoints) >= 1
    latest = engine.checkpointer.get_latest_checkpoint("proc-eng-100")
    assert latest is not None
    assert latest["state"]["process_id"] == "proc-eng-100"


def test_workflow_engine_resume() -> None:
    engine = WorkflowEngine()
    _ = engine.run(
        process_id="proc-eng-200",
        title="Resumable Process",
        instruction="Check supplier wire transfer",
        initial_context={"amount": 1200.0},
    )

    # Resume with updated state attributes
    resumed_state = engine.resume(
        process_id="proc-eng-200",
        resume_inputs={"human_approved": True, "notes": "Approved by CFO"},
    )
    assert resumed_state["process_id"] == "proc-eng-200"
    assert resumed_state["context"].get("human_approved") is True
    assert resumed_state["context"].get("notes") == "Approved by CFO"


def test_workflow_engine_resume_non_existent() -> None:
    engine = WorkflowEngine()
    with pytest.raises(ValueError, match="No checkpoint found"):
        engine.resume(process_id="non-existent-proc-id")
