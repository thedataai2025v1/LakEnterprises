"""Human approval interrupt node and decision routing (P11-1, P11-2)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from lakenterprises.workflow.escalation import EscalationRouter
from lakenterprises.workflow.state import WorkflowState, default_checkpointer
from lakenterprises.workflow.tracer import default_tracer

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def human_approval_node(state: WorkflowState) -> WorkflowState:
    """Evaluate or halt at human-in-the-loop review gate."""
    logger.info("Executing human_approval_node for process %s", state.get("process_id"))
    state = dict(state)
    proc_id = state.get("process_id", str(uuid.uuid4()))

    routing_history = list(state.get("routing_history", []))
    if "human_approval" not in routing_history:
        routing_history.append("human_approval")
    state["routing_history"] = routing_history
    state["active_node"] = "human_approval"
    state["current_step"] = "human_approval"

    # Check if process has already received a human decision
    decision = state.get("approval_decision") or {}
    status_str = (state.get("approval_status") or decision.get("status") or "").lower()

    if status_str == "approved":
        state["approval_status"] = "approved"
        state["status"] = "in_progress"
        state["current_status"] = "IN_PROGRESS"
        state["approval_required"] = False
        state["human_intervention_required"] = False

        history = list(state.get("history", []))
        history.append(
            {
                "step": "human_approval",
                "timestamp": _now_iso(),
                "status": "approved",
                "details": (
                    f"Approved by {decision.get('reviewed_by', 'Supervisor')}. "
                    f"Comment: {decision.get('comment', 'None')}"
                ),
            }
        )
        state["history"] = history

        default_tracer.emit(
            process_id=proc_id,
            event_type="approval_granted",
            step="human_approval",
            node_name="human_approval",
            payload=decision,
        )
        return state

    elif status_str == "rejected":
        state["approval_status"] = "rejected"
        state["status"] = "rejected"
        state["current_status"] = "REJECTED"
        state["approval_required"] = False
        state["human_intervention_required"] = False

        history = list(state.get("history", []))
        history.append(
            {
                "step": "human_approval",
                "timestamp": _now_iso(),
                "status": "rejected",
                "details": (
                    f"Rejected by {decision.get('reviewed_by', 'Supervisor')}. "
                    f"Reason: {decision.get('comment', 'Decision rejected')}"
                ),
            }
        )
        state["history"] = history

        default_tracer.emit(
            process_id=proc_id,
            event_type="approval_rejected",
            step="human_approval",
            node_name="human_approval",
            payload=decision,
        )
        return state

    # Otherwise, approval is required and pending
    # Evaluate escalation tier and SLA
    payload = state.get("input_payload") or state.get("context") or {}
    comp = state.get("compliance") or {}
    is_comp = comp.get("is_compliant", True)
    amount = float(payload.get("amount") or 0.0)
    risk_level = str(payload.get("severity") or comp.get("risk_level") or "LOW")

    tier, target_role, sla_hours, reason = EscalationRouter.evaluate_tier(
        amount=amount,
        risk_level=risk_level,
        has_violations=(not is_comp),
        severity_hint=payload.get("severity"),
    )
    sla_info = EscalationRouter.calculate_sla(
        tier=tier,
        created_at=state.get("history", [{}])[0].get("timestamp"),
        sla_hours_override=sla_hours,
        reason=reason,
    )

    app_id = state.get("approval_request_id") or f"appr-{uuid.uuid4().hex[:8]}"

    state["approval_request_id"] = app_id
    state["approval_required"] = True
    state["human_intervention_required"] = True
    state["approval_status"] = "pending"
    state["status"] = "awaiting_approval"
    state["current_status"] = "AWAITING_APPROVAL"
    state["escalation_tier"] = tier.value
    state["target_role"] = target_role
    state["sla_hours"] = sla_hours
    state["sla_deadline"] = sla_info.deadline
    state["sla_breached"] = sla_info.is_breached

    history = list(state.get("history", []))
    history.append(
        {
            "step": "human_approval",
            "timestamp": _now_iso(),
            "status": "paused_for_approval",
            "details": (
                f"Paused for {target_role} review [{tier.value}]. "
                f"SLA: {sla_hours}h (deadline: {sla_info.deadline}). Reason: {reason}"
            ),
        }
    )
    state["history"] = history

    default_checkpointer.record_checkpoint(proc_id, state, node_name="human_approval")
    default_tracer.emit(
        process_id=proc_id,
        event_type="approval_required",
        step="human_approval",
        node_name="human_approval",
        payload={
            "approval_request_id": app_id,
            "target_role": target_role,
            "tier": tier.value,
            "sla": sla_info.to_dict(),
            "amount": amount,
            "reason": reason,
        },
    )

    return state


def route_after_escalation(state: WorkflowState) -> str:
    """Route to human approval gate if review required, else execute resolution."""
    approval_required = state.get("approval_required") or state.get(
        "human_intervention_required"
    )
    status_str = (state.get("approval_status") or "").lower()

    if approval_required:
        if status_str == "approved":
            return "execute_resolution"
        elif status_str == "rejected":
            return "finalize"
        return "human_approval"
    return "execute_resolution"


def route_after_approval(state: WorkflowState) -> str:
    """Route after human approval evaluation."""
    status_str = (state.get("approval_status") or "").lower()
    if status_str == "approved":
        return "execute_resolution"
    return "finalize"
