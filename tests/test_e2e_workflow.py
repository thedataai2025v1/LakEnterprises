"""End-to-End integration test for Phase 10 Workflow Graph & Tracing.

Verifies:
1. End-to-end multi-agent workflow graph execution (Orchestrator -> Specialists -> Finalize).
2. Process state checkpointing and historical state inspection.
3. Event tracing pipeline and event log validation.
4. CLI workflow subcommand execution.
"""

from __future__ import annotations

import pytest

from lakenterprises.__main__ import main as cli_main
from lakenterprises.workflow import WorkflowEngine, global_checkpointer, global_tracer


def test_e2e_workflow_engine_execution() -> None:
    engine = WorkflowEngine()
    process_id = "proc-e2e-enterprise-01"

    final_state = engine.run(
        process_id=process_id,
        title="E2E Corporate Audit Investigation",
        instruction="Investigate unauthorized billing debit of $8,500.00 and check compliance policy",
        initial_context={"amount": 8500.0, "account_id": "ACC-54321"},
    )

    # 1. State assertions
    assert final_state["process_id"] == process_id
    assert final_state["title"] == "E2E Corporate Audit Investigation"
    assert final_state["current_status"] in ["COMPLETED", "ESCALATED"]
    assert "orchestrator" in final_state["routing_history"]
    assert final_state["confidence_score"] > 0.0

    # 2. Checkpointer verification
    checkpoints = global_checkpointer.list_checkpoints(process_id)
    assert len(checkpoints) >= 1
    assert any(
        cp["node_name"] in ["init", "finalize", "orchestrator"] for cp in checkpoints
    )

    # 3. Tracing verification
    events = global_tracer.get_events(process_id)
    assert len(events) >= 2
    event_types = [str(getattr(e.event_type, "value", e.event_type)) for e in events]
    assert any(
        t in event_types
        for t in [
            "process_started",
            "workflow_started",
            "workflow_completed",
            "node_completed",
        ]
    )


def test_e2e_workflow_cli_run(capsys: pytest.CaptureFixture[str]) -> None:
    # Run CLI command: lakenterprises workflow run --id proc-cli-e2e --title "CLI E2E"
    argv = [
        "workflow",
        "run",
        "--id",
        "proc-cli-e2e",
        "--title",
        "CLI E2E Process",
        "--instruction",
        "Audit suspicious wire transfer",
        "--amount",
        "15000",
    ]
    cli_main(argv)
    captured = capsys.readouterr()
    assert "Executing Enterprise Workflow Graph [Process: proc-cli-e2e]" in captured.out
    assert "Workflow Execution Completed:" in captured.out
    assert "Traced Events:" in captured.out


def test_e2e_workflow_cli_trace(capsys: pytest.CaptureFixture[str]) -> None:
    # Trace the previously executed CLI process
    argv = [
        "workflow",
        "trace",
        "--id",
        "proc-cli-e2e",
    ]
    cli_main(argv)
    captured = capsys.readouterr()
    assert "Trace Events for Process [proc-cli-e2e]" in captured.out
