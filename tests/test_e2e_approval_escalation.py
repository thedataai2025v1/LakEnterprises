"""End-to-End integration test for Phase 11 approval and escalation runtime (P11-5)."""

from __future__ import annotations

import pytest

from lakenterprises.__main__ import main as cli_main
from scripts.demo_e2e_process import run_e2e_process_demo


def test_e2e_process_demo_script_execution() -> None:
    resumed_state = run_e2e_process_demo()

    assert resumed_state["current_status"] == "COMPLETED"
    assert resumed_state["approval_status"] == "approved"
    assert "human_approval" in resumed_state["routing_history"]
    assert "execute_resolution" in resumed_state["routing_history"]
    assert resumed_state["resolution_execution"]["status"] == "executed"
    assert resumed_state["final_output"]["status"] == "completed"


def test_e2e_workflow_cli_demo_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    # Run CLI command: lakenterprises workflow demo
    argv = ["workflow", "demo"]
    cli_main(argv)

    captured = capsys.readouterr()
    assert "LAKENTERPRISES — END-TO-END PROCESS DEMO" in captured.out
    assert "Step 2: Workflow Paused at Human Approval Interrupt Gate!" in captured.out
    assert "Step 4: Executive Reviewer Reviews Findings & Signs Off" in captured.out
    assert "Step 6: Workflow Completed Successfully!" in captured.out
    assert "DEMO EXECUTION COMPLETE: 100% SUCCESS" in captured.out
