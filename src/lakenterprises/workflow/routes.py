"""FastAPI router endpoints for workflow graph execution and tracing (P10-5, P10-6)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from lakenterprises.workflow.graph import default_workflow_engine
from lakenterprises.workflow.state import default_checkpointer
from lakenterprises.workflow.tracer import WorkflowTraceEvent, default_tracer

router = APIRouter(prefix="/api/v1/workflow", tags=["workflow"])


class WorkflowRunRequest(BaseModel):
    """Payload to trigger execution of an enterprise workflow graph."""

    goal: str = ""
    instruction: Optional[str] = None
    title: Optional[str] = None
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None
    process_id: Optional[str] = None

    def get_goal(self) -> str:
        return self.goal or self.instruction or "Enterprise Investigation"

    def get_payload(self) -> Dict[str, Any]:
        return self.input_payload or self.context or {}


class WorkflowResumeRequest(BaseModel):
    """Payload to resume a paused or checkpointed process."""

    updates: Dict[str, Any] = Field(default_factory=dict)
    resume_inputs: Optional[Dict[str, Any]] = None

    def get_updates(self) -> Dict[str, Any]:
        return self.updates or self.resume_inputs or {}


@router.post(
    "/run",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Execute enterprise multi-agent workflow graph",
)
def run_workflow(request: WorkflowRunRequest) -> Dict[str, Any]:
    """Execute the full StateGraph workflow across specialist agents."""
    state = default_workflow_engine.run(
        goal=request.get_goal(),
        input_payload=request.get_payload(),
        process_id=request.process_id,
        title=request.title,
    )
    return dict(state)


@router.get(
    "/{process_id}/state",
    response_model=Dict[str, Any],
    summary="Retrieve latest checkpointed state for a process",
)
def get_workflow_state(process_id: str) -> Dict[str, Any]:
    """Fetch the latest state checkpoint from the checkpointer."""
    state = default_checkpointer.get_latest_state(process_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Process '{process_id}' not found in checkpointer.",
        )
    return dict(state)


@router.post(
    "/{process_id}/resume",
    response_model=Dict[str, Any],
    summary="Resume execution of a paused or checkpointed process",
)
def resume_workflow(
    process_id: str,
    request: WorkflowResumeRequest,
) -> Dict[str, Any]:
    """Resume execution of an existing workflow thread from its last checkpoint."""
    try:
        final_state = default_workflow_engine.resume(
            process_id=process_id, updates=request.get_updates()
        )
        return dict(final_state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{process_id}/events",
    response_model=List[WorkflowTraceEvent],
    summary="Fetch all telemetry and trace events for a process",
)
def get_workflow_events(process_id: str) -> List[WorkflowTraceEvent]:
    """Fetch the complete event stream recorded by WorkflowTracer."""
    return default_tracer.get_events(process_id)


@router.get(
    "/{process_id}/checkpoints",
    response_model=List[Dict[str, Any]],
    summary="List all recorded state snapshots for a process",
)
def list_workflow_checkpoints(process_id: str) -> List[Dict[str, Any]]:
    """List snapshots recorded for audit replay and time-travel inspection."""
    return default_checkpointer.list_checkpoints(process_id)
