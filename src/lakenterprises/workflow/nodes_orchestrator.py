"""Orchestrator graph nodes and routing logic (P10-2)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from lakenterprises.agents.supervisor import SupervisorAgent
from lakenterprises.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def orchestrator_node(state: WorkflowState) -> WorkflowState:
    """Supervisory node that evaluates the goal and generates the execution plan."""
    logger.info("Executing orchestrator_node for process %s", state.get("process_id"))
    state = dict(state)  # copy state

    supervisor = SupervisorAgent()
    goal = state.get("goal", "")
    payload = state.get("input_payload", {})

    plan = supervisor.plan_workflow(goal, context=payload)
    plan_dict = plan.model_dump()

    state["plan"] = plan_dict
    state["current_step"] = "orchestrator"
    state["active_node"] = "orchestrator"
    state["status"] = "in_progress"
    state["current_status"] = "IN_PROGRESS"

    routing_history = list(state.get("routing_history", []))
    if "orchestrator" not in routing_history:
        routing_history.append("orchestrator")
    state["routing_history"] = routing_history

    agent_outputs = dict(state.get("agent_outputs", {}))
    agent_outputs["supervisor"] = plan_dict
    state["agent_outputs"] = agent_outputs

    history = list(state.get("history", []))
    history.append(
        {
            "step": "orchestrator",
            "timestamp": _now_iso(),
            "status": "planned",
            "details": (
                f"Planned {len(plan.planned_agents)} specialist agents: "
                f"{', '.join([a.value for a in plan.planned_agents])}"
            ),
        }
    )
    state["history"] = history
    return state


def route_orchestrator(state: WorkflowState) -> str:
    """Determine the next specialist agent node following orchestration planning."""
    plan = state.get("plan") or {}
    planned = plan.get("planned_agents", [])

    if "document_analyst" in planned:
        return "document_analyst"
    if "compliance" in planned:
        return "compliance"
    if "knowledge_retriever" in planned:
        return "knowledge_retriever"
    return "finalize"
