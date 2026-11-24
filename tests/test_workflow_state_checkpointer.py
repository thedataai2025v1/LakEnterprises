"""Unit tests for Phase 10 process state and checkpointer."""

from __future__ import annotations

from lakenterprises.workflow.state import (
    ProcessStateCheckpointer,
    create_initial_workflow_state,
)


def test_create_initial_workflow_state_defaults() -> None:
    state = create_initial_workflow_state(
        process_id="proc-101",
        title="Test Dispute Investigation",
        instruction="Verify vendor payment dispute",
    )
    assert state["process_id"] == "proc-101"
    assert state["title"] == "Test Dispute Investigation"
    assert state["instruction"] == "Verify vendor payment dispute"
    assert state["current_status"] == "PENDING"
    assert state["active_node"] == "orchestrator"
    assert state["human_intervention_required"] is False
    assert state["confidence_score"] == 1.0
    assert state["iteration_count"] == 0
    assert state["citations"] == []
    assert state["routing_history"] == []
    assert state["agent_outputs"] == {}


def test_create_initial_workflow_state_custom_context() -> None:
    context = {"customer_id": "CUST-999", "amount": 12500.0}
    state = create_initial_workflow_state(
        process_id="proc-102",
        title="Custom Context Proc",
        instruction="Check high value wire",
        initial_context=context,
    )
    assert state["context"]["customer_id"] == "CUST-999"
    assert state["context"]["amount"] == 12500.0


def test_process_state_checkpointer_save_and_retrieve() -> None:
    checkpointer = ProcessStateCheckpointer()
    state = create_initial_workflow_state(
        "proc-201", "Checkpointer Test", "Test instruction"
    )

    snap1 = checkpointer.save_checkpoint("proc-201", state, node_name="start")
    assert snap1["process_id"] == "proc-201"
    assert snap1["step_number"] == 1
    assert snap1["node_name"] == "start"

    # Mutate state copy and save step 2
    state2 = dict(state)
    state2["current_status"] = "IN_PROGRESS"
    state2["active_node"] = "document_analyst"
    snap2 = checkpointer.save_checkpoint(
        "proc-201", state2, node_name="document_analyst"
    )
    assert snap2["step_number"] == 2

    # Check latest checkpoint
    latest = checkpointer.get_latest_checkpoint("proc-201")
    assert latest is not None
    assert latest["step_number"] == 2
    assert latest["state"]["current_status"] == "IN_PROGRESS"

    # Check step 1 retrieval
    step1_retrieved = checkpointer.get_checkpoint("proc-201", step_number=1)
    assert step1_retrieved is not None
    assert step1_retrieved["state"]["current_status"] == "PENDING"


def test_process_state_checkpointer_list_and_rewind() -> None:
    checkpointer = ProcessStateCheckpointer()
    state = create_initial_workflow_state("proc-301", "Rewind Test", "Test rewind")

    checkpointer.save_checkpoint("proc-301", state, node_name="node1")
    state2 = dict(state)
    state2["routing_history"] = ["node1"]
    checkpointer.save_checkpoint("proc-301", state2, node_name="node2")

    history = checkpointer.list_checkpoints("proc-301")
    assert len(history) == 2
    assert history[0]["step_number"] == 1
    assert history[1]["step_number"] == 2

    # Rewind to step 1
    rewound = checkpointer.rewind_to_checkpoint("proc-301", step_number=1)
    assert rewound is not None
    assert rewound["routing_history"] == []

    # Rewind to non-existent step
    assert checkpointer.rewind_to_checkpoint("proc-301", step_number=99) is None
    assert checkpointer.get_latest_checkpoint("non-existent-proc") is None
