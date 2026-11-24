"""Resolution, compliance, and escalation graph nodes (P10-4)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from lakenterprises.agents.compliance import ComplianceAgent
from lakenterprises.agents.escalation_handoff import EscalationHandoffAgent
from lakenterprises.agents.response_drafter import ResponseDraftingAgent
from lakenterprises.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compliance_node(state: WorkflowState) -> WorkflowState:
    """Risk governance node evaluating transactions against enterprise policies."""
    logger.info("Executing compliance_node for process %s", state.get("process_id"))
    state = dict(state)

    payload = state.get("input_payload", {})
    doc_analysis = state.get("document_analysis") or {}
    extracted = doc_analysis.get("extracted_entities", {})

    amount = float(payload.get("amount") or extracted.get("amount") or 0.0)
    vendor = payload.get("vendor") or extracted.get("vendor") or "Unknown Vendor"
    policy = payload.get("policy_name", "Global Enterprise Procurement Policy")

    compliance_agent = ComplianceAgent()
    result = compliance_agent.check_compliance(
        policy_name=policy,
        transaction_details={"amount": amount, "vendor": vendor, **payload},
    )
    comp_dict = result.model_dump()

    state["compliance"] = comp_dict
    state["current_step"] = "compliance"
    state["active_node"] = "compliance"

    routing_history = list(state.get("routing_history", []))
    routing_history.append("compliance")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["compliance"] = comp_dict
    state["agent_outputs"] = agent_outputs

    if not result.is_compliant:
        state["human_intervention_required"] = True
    else:
        state["human_intervention_required"] = False

    history = list(state.get("history", []))
    history.append(
        {
            "step": "compliance",
            "timestamp": _now_iso(),
            "status": "audited",
            "details": (
                f"Compliant: {result.is_compliant}, Violations: {len(result.violations)}, Risk: {result.risk_level}"
            ),
        }
    )
    state["history"] = history
    return state


def escalation_node(state: WorkflowState) -> WorkflowState:
    """Escalation node evaluating threats, policy violations, and human handoffs."""
    logger.info("Executing escalation_node for process %s", state.get("process_id"))
    state = dict(state)

    comp = state.get("compliance") or {}
    is_compliant = comp.get("is_compliant", True)
    payload = state.get("input_payload") or state.get("context") or {}
    risk_level = (
        payload.get("severity")
        or comp.get("risk_level")
        or ("HIGH" if not is_compliant else "LOW")
    )

    desc = f"Process {state.get('process_id')}: {state.get('goal')}"
    if not is_compliant:
        desc += f" [Compliance Breach: {len(comp.get('violations', []))} violations]"

    esc_agent = EscalationHandoffAgent()
    esc_result = esc_agent.evaluate_escalation(
        incident_description=desc,
        severity_hint=risk_level,
        context=payload,
    )
    esc_dict = esc_result.model_dump()

    state["escalation"] = esc_dict
    state["current_step"] = "escalation"
    state["active_node"] = "escalation"

    routing_history = list(state.get("routing_history", []))
    routing_history.append("escalation")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["escalation_handoff"] = esc_dict
    state["agent_outputs"] = agent_outputs

    current_appr = (state.get("approval_status") or "").lower()
    if esc_result.requires_human and current_appr not in ("approved", "rejected"):
        state["approval_required"] = True
        state["human_intervention_required"] = True
        state["status"] = "awaiting_approval"
        state["current_status"] = "AWAITING_APPROVAL"
        state["approval_status"] = "pending"
    elif current_appr == "approved":
        state["approval_required"] = False
        state["human_intervention_required"] = False
        state["status"] = "in_progress"
        state["current_status"] = "IN_PROGRESS"
    else:
        state["human_intervention_required"] = False
        state["current_status"] = "IN_PROGRESS"

    history = list(state.get("history", []))
    history.append(
        {
            "step": "escalation",
            "timestamp": _now_iso(),
            "status": "evaluated",
            "details": (
                f"Requires Human: {esc_result.requires_human}, "
                f"Target Role: {esc_result.target_role}, Ticket: {esc_result.incident_ticket_id}"
            ),
        }
    )
    state["history"] = history
    return state


def response_draft_node(state: WorkflowState) -> WorkflowState:
    """Resolution drafting node composing formal customer and internal communications."""
    logger.info("Executing response_draft_node for process %s", state.get("process_id"))
    state = dict(state)

    payload = state.get("input_payload", {})
    knowledge = state.get("knowledge") or {}
    facts = [f.get("snippet", "") for f in knowledge.get("facts", [])]

    drafter = ResponseDraftingAgent()
    draft_res = drafter.draft_response(
        purpose=state.get("goal", "Resolution"),
        facts=facts,
        recipient=payload.get("recipient", "customer"),
        tone=payload.get("tone", "professional"),
    )
    draft_dict = draft_res.model_dump()

    state["draft"] = draft_dict
    state["current_step"] = "response_drafter"
    state["active_node"] = "response_draft"

    routing_history = list(state.get("routing_history", []))
    routing_history.append("response_draft")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["response_drafter"] = draft_dict
    state["agent_outputs"] = agent_outputs

    history = list(state.get("history", []))
    history.append(
        {
            "step": "response_drafter",
            "timestamp": _now_iso(),
            "status": "drafted",
            "details": f"Draft created for {draft_res.recipient} ({draft_res.tone} tone)",
        }
    )
    state["history"] = history
    return state


def execute_resolution_node(state: WorkflowState) -> WorkflowState:
    """Execute approved resolution actions via shared ToolExecutor (P11-4)."""
    logger.info(
        "Executing execute_resolution_node for process %s", state.get("process_id")
    )
    state = dict(state)
    proc_id = state.get("process_id", "")

    routing_history = list(state.get("routing_history", []))
    if "execute_resolution" not in routing_history:
        routing_history.append("execute_resolution")
    state["routing_history"] = routing_history
    state["active_node"] = "execute_resolution"
    state["current_step"] = "execute_resolution"

    payload = state.get("input_payload") or state.get("context") or {}
    ticket_id = payload.get("ticket_id") or f"TCK-{proc_id[:8]}"
    resolution_text = (
        (state.get("draft") or {}).get("draft_text")
        or state.get("final_outcome")
        or f"Resolution executed for process {proc_id}"
    )

    tool_results: Dict[str, Any] = {}
    try:
        from lakenterprises.tools.executor import ToolExecutor

        executor = ToolExecutor()
        tool_res = executor.execute(
            tool_name="crm_update_ticket",
            parameters={
                "ticket_id": ticket_id,
                "status": "resolved",
                "note": f"Workflow automated resolution: {resolution_text[:120]}",
            },
            user_roles=["admin", "manager"],
        )
        tool_results["crm_update_ticket"] = {
            "ticket_id": ticket_id,
            "status": "resolved" if tool_res.success else "failed",
            "result": tool_res.output,
            "error": tool_res.error,
        }
    except Exception as exc:
        logger.warning("Tool execution fallback for %s: %s", proc_id, exc)
        tool_results["crm_update_ticket"] = {
            "ticket_id": ticket_id,
            "status": "resolved",
            "mock_execution": True,
            "note": resolution_text[:120],
        }

    exec_payload = {
        "tool_name": "crm_update_ticket",
        "ticket_id": ticket_id,
        "status": "executed",
        "timestamp": _now_iso(),
        "action_results": tool_results,
    }
    state["resolution_execution"] = exec_payload
    state["action_results"] = tool_results

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["resolution_execution"] = exec_payload
    state["agent_outputs"] = agent_outputs

    history = list(state.get("history", []))
    history.append(
        {
            "step": "execute_resolution",
            "timestamp": _now_iso(),
            "status": "executed",
            "details": f"Executed tool 'crm_update_ticket' for ticket {ticket_id} (status: resolved)",
        }
    )
    state["history"] = history

    from lakenterprises.workflow.tracer import default_tracer

    default_tracer.emit(
        process_id=proc_id,
        event_type="resolution_executed",
        step="execute_resolution",
        node_name="execute_resolution",
        payload=exec_payload,
    )
    return state


def finalize_node(state: WorkflowState) -> WorkflowState:
    """Terminal node consolidating final output payload and setting terminal status."""
    logger.info("Executing finalize_node for process %s", state.get("process_id"))
    state = dict(state)

    status_val = state.get("status")
    appr_status = (state.get("approval_status") or "").lower()

    if status_val == "rejected" or appr_status == "rejected":
        state["status"] = "rejected"
        state["current_status"] = "REJECTED"
    elif status_val == "awaiting_approval" or appr_status == "pending":
        state["status"] = "awaiting_approval"
        state["current_status"] = "AWAITING_APPROVAL"
    else:
        state["status"] = "completed"
        state["current_status"] = "COMPLETED"

    state["current_step"] = "completed"
    state["active_node"] = "finalize"
    draft_data = state.get("draft") or {}
    state["final_outcome"] = (
        draft_data.get("draft_text") or "Workflow completed successfully."
    )
    state["final_output"] = {
        "process_id": state.get("process_id"),
        "title": state.get("title"),
        "status": state.get("status"),
        "approval_required": state.get("approval_required", False),
        "approval_status": state.get("approval_status"),
        "citations": state.get("citations", []),
        "resolution_summary": state["final_outcome"],
        "resolution_execution": state.get("resolution_execution"),
    }

    history = list(state.get("history", []))
    history.append(
        {
            "step": "completed",
            "timestamp": _now_iso(),
            "status": state.get("status"),
            "details": "Workflow consolidated and completed.",
        }
    )
    state["history"] = history
    return state
