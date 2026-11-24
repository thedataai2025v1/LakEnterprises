"""Workflow state definitions and checkpointer for LangGraph execution (P10-1)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowState(TypedDict, total=False):
    """Complete state carried through the LangGraph workflow graph."""

    process_id: str
    title: str
    status: str  # pending, in_progress, awaiting_approval, completed, failed
    current_status: str
    current_step: str
    active_node: str
    instruction: str
    goal: str
    input_payload: Dict[str, Any]
    context: Dict[str, Any]
    plan: Optional[Dict[str, Any]]
    document_analysis: Optional[Dict[str, Any]]
    compliance: Optional[Dict[str, Any]]
    knowledge: Optional[Dict[str, Any]]
    draft: Optional[Dict[str, Any]]
    escalation: Optional[Dict[str, Any]]
    approval_required: bool
    human_intervention_required: bool
    approval_request_id: Optional[str]
    approval_status: Optional[str]  # pending, approved, rejected
    confidence_score: float
    iteration_count: int
    routing_history: List[str]
    agent_outputs: Dict[str, Any]
    collected_documents: List[Dict[str, Any]]
    history: List[Dict[str, Any]]
    citations: List[str]
    error: Optional[str]
    final_output: Optional[Dict[str, Any]]
    final_outcome: Optional[str]


def create_initial_workflow_state(
    goal: str = "",
    process_id: Optional[str] = None,
    title: Optional[str] = None,
    input_payload: Optional[Dict[str, Any]] = None,
    instruction: Optional[str] = None,
    initial_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a clean initial state for a new enterprise workflow process."""
    proc_id = process_id or str(uuid.uuid4())
    effective_goal = goal or instruction or "Enterprise investigation process"
    effective_payload = input_payload or initial_context or {}
    effective_title = title or f"Process: {effective_goal[:40]}"

    return {
        "process_id": proc_id,
        "title": effective_title,
        "instruction": effective_goal,
        "goal": effective_goal,
        "status": "pending",
        "current_status": "PENDING",
        "current_step": "init",
        "active_node": "orchestrator",
        "input_payload": effective_payload,
        "context": effective_payload,
        "plan": None,
        "document_analysis": None,
        "compliance": None,
        "knowledge": None,
        "draft": None,
        "escalation": None,
        "approval_required": False,
        "human_intervention_required": False,
        "approval_request_id": None,
        "approval_status": None,
        "confidence_score": 1.0,
        "iteration_count": 0,
        "routing_history": [],
        "agent_outputs": {},
        "collected_documents": [],
        "history": [
            {
                "step": "init",
                "timestamp": _now_iso(),
                "status": "initialized",
                "details": f"Process {proc_id} initialized.",
            }
        ],
        "citations": [],
        "error": None,
        "final_output": None,
        "final_outcome": None,
    }


class ProcessStateCheckpointer:
    """Checkpointer managing checkpoint persistence, retrieval, and replay."""

    def __init__(self, memory_saver: Optional[MemorySaver] = None) -> None:
        self._saver = memory_saver or MemorySaver()
        self._custom_state_store: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def checkpointer(self) -> MemorySaver:
        """Return the LangGraph-compatible checkpointer."""
        return self._saver

    def record_checkpoint(
        self,
        process_id: str,
        state: Dict[str, Any],
        node_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an explicit snapshot of the workflow state for audit and resume."""
        if process_id not in self._custom_state_store:
            self._custom_state_store[process_id] = []
        step_number = len(self._custom_state_store[process_id]) + 1
        snapshot = {
            "checkpoint_id": str(uuid.uuid4()),
            "process_id": process_id,
            "step_number": step_number,
            "node_name": node_name
            or state.get("active_node")
            or state.get("current_step", "unknown"),
            "timestamp": _now_iso(),
            "step": state.get("current_step", "unknown"),
            "status": state.get("status", "unknown"),
            "state": dict(state),
        }
        self._custom_state_store[process_id].append(snapshot)
        return snapshot

    def save_checkpoint(
        self,
        process_id: str,
        state: Dict[str, Any],
        node_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for record_checkpoint."""
        return self.record_checkpoint(process_id, state, node_name=node_name)

    def get_latest_state(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent state dict for a process."""
        history = self._custom_state_store.get(process_id)
        if history:
            return history[-1]["state"]
        return None

    def get_latest_checkpoint(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent checkpoint snapshot for a process."""
        history = self._custom_state_store.get(process_id)
        if history:
            return history[-1]
        return None

    def get_checkpoint(
        self, process_id: str, step_number: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a specific step's checkpoint snapshot."""
        for snap in self._custom_state_store.get(process_id, []):
            if snap.get("step_number") == step_number:
                return snap
        return None

    def list_checkpoints(self, process_id: str) -> List[Dict[str, Any]]:
        """List all checkpoint snapshots for a process."""
        return list(self._custom_state_store.get(process_id, []))

    def rewind_to_checkpoint(
        self, process_id: str, step_number: int
    ) -> Optional[Dict[str, Any]]:
        """Rewind process to a specific checkpoint state."""
        snap = self.get_checkpoint(process_id, step_number)
        if snap:
            return dict(snap["state"])
        return None


default_checkpointer = ProcessStateCheckpointer()
global_checkpointer = default_checkpointer
