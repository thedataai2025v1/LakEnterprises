"""LangGraph StateGraph assembly and execution engine (P10-5)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from lakenterprises.workflow.nodes_investigate import (
    document_analyst_node,
    knowledge_retriever_node,
)
from lakenterprises.workflow.nodes_orchestrator import orchestrator_node
from lakenterprises.workflow.nodes_resolution import (
    compliance_node,
    escalation_node,
    finalize_node,
    response_draft_node,
)
from lakenterprises.workflow.state import (
    ProcessStateCheckpointer,
    WorkflowState,
    create_initial_workflow_state,
    default_checkpointer,
)
from lakenterprises.workflow.tracer import WorkflowTracer, default_tracer

logger = logging.getLogger(__name__)


def build_enterprise_workflow_graph(checkpointer: Optional[Any] = None) -> Any:
    """Build and compile the enterprise multi-agent LangGraph workflow graph."""
    graph = StateGraph(WorkflowState)

    # 1. Register all specialist and lifecycle nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("document_analyst", document_analyst_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("knowledge_retriever", knowledge_retriever_node)
    graph.add_node("response_drafter", response_draft_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("finalize", finalize_node)

    # 2. Wire sequential and conditional transitions
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "document_analyst")
    graph.add_edge("document_analyst", "compliance")
    graph.add_edge("compliance", "knowledge_retriever")
    graph.add_edge("knowledge_retriever", "response_drafter")
    graph.add_edge("response_drafter", "escalation")
    graph.add_edge("escalation", "finalize")
    graph.add_edge("finalize", END)

    # 3. Compile graph with checkpointer
    if isinstance(checkpointer, ProcessStateCheckpointer):
        cp = checkpointer.checkpointer
    else:
        cp = (
            checkpointer
            if checkpointer is not None
            else default_checkpointer.checkpointer
        )
    return graph.compile(checkpointer=cp)


class WorkflowEngine:
    """High-level runner managing process lifecycle, checkpoints, and event tracing."""

    def __init__(
        self,
        checkpointer: Optional[ProcessStateCheckpointer] = None,
        tracer: Optional[WorkflowTracer] = None,
    ) -> None:
        self.checkpointer = checkpointer or default_checkpointer
        self.tracer = tracer or default_tracer
        self.compiled_graph = build_enterprise_workflow_graph(
            self.checkpointer.checkpointer
        )

    def run(
        self,
        goal: str = "",
        input_payload: Optional[Dict[str, Any]] = None,
        process_id: Optional[str] = None,
        title: Optional[str] = None,
        instruction: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """Execute the enterprise workflow graph from start to completion."""
        effective_goal = goal or instruction or "Enterprise investigation process"
        effective_payload = input_payload or initial_context or {}

        initial_state = create_initial_workflow_state(
            goal=effective_goal,
            process_id=process_id,
            title=title,
            input_payload=effective_payload,
        )
        proc_id = initial_state["process_id"]

        self.tracer.emit(
            process_id=proc_id,
            event_type="workflow_started",
            step="init",
            node_name="orchestrator",
            payload={"goal": effective_goal},
        )
        self.checkpointer.record_checkpoint(proc_id, initial_state, node_name="init")

        # Thread configuration for LangGraph checkpoint isolation
        config = {"configurable": {"thread_id": proc_id}}

        try:
            raw_final = self.compiled_graph.invoke(initial_state, config=config)
            final_state = dict(raw_final)
            if "context" not in final_state or not final_state["context"]:
                final_state["context"] = dict(initial_state.get("context", {}))
            if "current_status" not in final_state:
                final_state["current_status"] = final_state.get(
                    "status", "completed"
                ).upper()
            if (
                "routing_history" not in final_state
                or not final_state["routing_history"]
            ):
                final_state["routing_history"] = [
                    h["step"] for h in final_state.get("history", [])
                ]
            self.checkpointer.record_checkpoint(proc_id, final_state)

            event_type = (
                "approval_required"
                if final_state.get("approval_required")
                else "workflow_completed"
            )
            self.tracer.emit(
                process_id=proc_id,
                event_type=event_type,
                step=final_state.get("current_step", "completed"),
                payload=final_state.get("final_output", {}),
            )
            return final_state

        except Exception as exc:
            logger.error("Workflow run failed for process %s: %s", proc_id, exc)
            err_state = dict(initial_state)
            err_state["status"] = "failed"
            err_state["error"] = str(exc)
            self.checkpointer.record_checkpoint(proc_id, err_state)
            self.tracer.emit(
                process_id=proc_id,
                event_type="workflow_failed",
                step=err_state.get("current_step", "error"),
                payload={"error": str(exc)},
            )
            return err_state

    def resume(
        self,
        process_id: str,
        updates: Optional[Dict[str, Any]] = None,
        resume_inputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """Resume execution of a paused or checkpointed process."""
        latest_state = self.checkpointer.get_latest_state(process_id)
        if not latest_state:
            raise ValueError(
                f"No checkpoint found: Process {process_id} not found in checkpointer."
            )

        state = dict(latest_state)
        effective_updates = updates or resume_inputs or {}
        if effective_updates:
            state.update(effective_updates)
            context = dict(state.get("context", {}))
            context.update(effective_updates)
            state["context"] = context

        self.tracer.emit(
            process_id=process_id,
            event_type="workflow_resumed",
            step=state.get("current_step", "resume"),
            payload=effective_updates,
        )

        config = {"configurable": {"thread_id": process_id}}
        raw_final = self.compiled_graph.invoke(state, config=config)
        final_state = dict(raw_final)
        if "context" not in final_state or not final_state["context"]:
            final_state["context"] = dict(state.get("context", {}))
        if "current_status" not in final_state:
            final_state["current_status"] = final_state.get(
                "status", "completed"
            ).upper()
        self.checkpointer.record_checkpoint(process_id, final_state, node_name="resume")
        return final_state


default_workflow_engine = WorkflowEngine()
global_engine = default_workflow_engine
