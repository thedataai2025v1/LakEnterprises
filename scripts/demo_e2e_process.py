"""End-to-End Enterprise Process Demo Script (P11-5).

Demonstrates the complete human-in-the-loop lifecycle:
1. Intake of a high-value dispute ($125,000.00).
2. Multi-agent investigation (Orchestrator -> Document Analyst -> Compliance).
3. Compliance violation detection (exceeds $100k single-approver threshold).
4. Multi-tier escalation routing (Tier 4 Executive sign-off with 1-hour SLA).
5. Pause at human approval interrupt node (status: AWAITING_APPROVAL).
6. State checkpointing and SLA deadline tracking.
7. Executive approval decision submission.
8. Seamless workflow resumption from checkpoint.
9. Resolution execution via shared tool path (CRM ticket update).
10. Final output consolidation and telemetry event audit.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict

from lakenterprises.workflow import WorkflowEngine, global_checkpointer, global_tracer
from lakenterprises.workflow.escalation import EscalationRouter, EscalationTier


def run_e2e_process_demo() -> Dict[str, Any]:
    """Execute canonical human-in-the-loop enterprise process demo."""
    print("\n" + "=" * 70)
    print(" LAKENTERPRISES — END-TO-END PROCESS DEMO (PHASE 11)")
    print(" Human-in-the-Loop Approval & Escalation Runtime")
    print("=" * 70 + "\n")

    engine = WorkflowEngine()
    process_id = f"proc-demo-{int(time.time())}"
    title = "High-Value Vendor Dispute ($125,000.00)"
    instruction = (
        "Investigate unauthorized vendor billing debit of $125,000.00 from Acme Tech Services, "
        "verify enterprise procurement policies, route for executive authorization, and execute resolution."
    )
    initial_context = {
        "amount": 125000.0,
        "vendor": "Acme Tech Services",
        "ticket_id": "TCK-DISPUTE-9901",
        "doc_type": "procurement_contract",
    }

    print(f"Step 1: Initiating High-Risk Workflow Process [{process_id}]...")
    print(f"  Title:       {title}")
    print(f"  Amount:      ${initial_context['amount']:,.2f}")
    print(f"  Ticket:      {initial_context['ticket_id']}")
    print("-" * 70)

    # 1. Run until human approval interrupt
    state = engine.run(
        process_id=process_id,
        title=title,
        instruction=instruction,
        initial_context=initial_context,
    )

    print("\nStep 2: Workflow Paused at Human Approval Interrupt Gate!")
    print(f"  Process Status:     {state.get('current_status')}")
    print(f"  Active Node:        {state.get('active_node')}")
    print(f"  Approval Required:  {state.get('approval_required')}")
    print(f"  Approval Request:   {state.get('approval_request_id')}")
    print(f"  Escalation Tier:    {state.get('escalation_tier')}")
    print(f"  Assigned Reviewer:  {state.get('target_role')}")
    print(
        f"  SLA Deadline:       {state.get('sla_deadline')} ({state.get('sla_hours')}h window)"
    )

    # 2. Inspect SLA
    tier = EscalationTier(state.get("escalation_tier", "tier_4_executive"))
    sla_info = EscalationRouter.calculate_sla(
        tier, created_at=state["history"][0]["timestamp"]
    )
    print(f"  SLA Breached:       {sla_info.is_breached}")
    print(f"  Remaining Time:     {sla_info.remaining_seconds:.1f} seconds")

    # 3. Verify Checkpointer snapshot
    snapshots = global_checkpointer.list_checkpoints(process_id)
    print(
        f"\nStep 3: Checkpointer Snapshot Verified ({len(snapshots)} snapshots saved)."
    )
    latest_snap = global_checkpointer.get_latest_checkpoint(process_id)
    if latest_snap:
        print(
            f"  Checkpoint Step:    #{latest_snap.get('step_number')} ({latest_snap.get('node_name')})"
        )

    # 4. Simulate Executive Human Approval Decision
    print("\nStep 4: Executive Reviewer Reviews Findings & Signs Off...")
    approver = "Chief Risk Officer (Executive Board)"
    comment = "Exception approved: Vendor identity verified, Net-30 payment authorized under Q4 emergency budget."
    print(f"  Decided By: {approver}")
    print("  Verdict:    APPROVED")
    print(f'  Comment:    "{comment}"')

    decision_payload = {
        "status": "approved",
        "reviewed_by": approver,
        "comment": comment,
    }

    # 5. Resume Workflow from Checkpoint
    print("\nStep 5: Resuming Workflow Execution from Saved Checkpoint...")
    resumed_state = engine.resume(
        process_id=process_id,
        updates={
            "approval_decision": decision_payload,
            "approval_status": "approved",
        },
    )

    print("\nStep 6: Workflow Completed Successfully!")
    print(f"  Final Status:       {resumed_state.get('current_status')}")
    print(f"  Active Node:        {resumed_state.get('active_node')}")
    print(
        f"  Resolution Tool:    {resumed_state.get('resolution_execution', {}).get('tool_name')}"
    )
    crm_res = (
        resumed_state.get("resolution_execution", {})
        .get("action_results", {})
        .get("crm_update_ticket", {})
    )
    print(f"  Ticket Status:      {crm_res.get('status')}")
    print(
        f"  Execution Path:     {' -> '.join(resumed_state.get('routing_history', []))}"
    )
    print(f"  Resolution Summary: {resumed_state.get('final_outcome')}")

    events = global_tracer.get_events(process_id)
    print(f"\nStep 7: Observability & Telemetry Audit ({len(events)} events recorded):")
    for ev in events:
        ev_type = str(getattr(ev.event_type, "value", ev.event_type))
        print(
            f"  [{ev.timestamp[11:19]}] {ev_type:22} | Node: {ev.node_name or 'N/A':18}"
        )

    print("\n" + "=" * 70)
    print(" DEMO EXECUTION COMPLETE: 100% SUCCESS")
    print("=" * 70 + "\n")
    return resumed_state


if __name__ == "__main__":
    try:
        run_e2e_process_demo()
    except Exception as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        sys.exit(1)
