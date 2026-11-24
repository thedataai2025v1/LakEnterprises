"""Workflow tracer and event streaming telemetry (P10-6)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceEventType(str, Enum):
    """Telemetry event types for workflow execution tracking."""

    PROCESS_STARTED = "process_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    APPROVAL_REQUIRED = "approval_required"
    PROCESS_COMPLETED = "process_completed"
    ERROR = "error"


class WorkflowTraceEvent(BaseModel):
    """Structured telemetry event emitted during workflow execution."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    process_id: str
    event_type: str  # e.g., TraceEventType or string
    node_name: Optional[str] = None
    step_number: Optional[int] = None
    step: str = ""
    timestamp: str = Field(default_factory=_now_utc_iso)
    payload: Dict[str, Any] = Field(default_factory=dict)


class WorkflowTracer:
    """In-memory event bus and telemetry tracer for workflow processes."""

    def __init__(self) -> None:
        self._events: Dict[str, List[WorkflowTraceEvent]] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def emit(
        self,
        process_id: str,
        event_type: str | TraceEventType,
        step: str = "",
        node_name: Optional[str] = None,
        step_number: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowTraceEvent:
        """Record and broadcast a workflow telemetry event."""
        type_str = (
            event_type.value
            if isinstance(event_type, TraceEventType)
            else str(event_type)
        )
        resolved_step = step or node_name or ""
        resolved_node = node_name or (step if step else None)

        event = WorkflowTraceEvent(
            process_id=process_id,
            event_type=type_str,
            node_name=resolved_node,
            step_number=step_number,
            step=resolved_step,
            payload=payload or {},
        )

        if process_id not in self._events:
            self._events[process_id] = []
        self._events[process_id].append(event)

        logger.info(
            "[WorkflowTracer] %s | %s | node: %s | step: %s",
            process_id,
            type_str,
            resolved_node,
            step_number,
        )

        # Notify any active async subscribers
        if process_id in self._subscribers:
            for q in self._subscribers[process_id]:
                try:
                    q.put_nowait(event)
                except Exception as exc:
                    logger.debug("Failed to put event in queue: %s", exc)

        return event

    def get_events(
        self,
        process_id: str,
        event_type: Optional[str | TraceEventType] = None,
        node_name: Optional[str] = None,
    ) -> List[WorkflowTraceEvent]:
        """Fetch historical trace events for a process with optional filtering."""
        events = list(self._events.get(process_id, []))
        if event_type is not None:
            type_str = (
                event_type.value
                if isinstance(event_type, TraceEventType)
                else str(event_type)
            )
            events = [e for e in events if e.event_type == type_str]
        if node_name is not None:
            events = [e for e in events if e.node_name == node_name]
        return events

    def clear(self, process_id: Optional[str] = None) -> None:
        """Clear recorded events for a process or all processes."""
        if process_id:
            self._events.pop(process_id, None)
            self._subscribers.pop(process_id, None)
        else:
            self._events.clear()
            self._subscribers.clear()

    async def stream_events(
        self,
        process_id: str,
        timeout_seconds: float = 30.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Asynchronously stream trace events as SSE chunks."""
        queue: asyncio.Queue[WorkflowTraceEvent] = asyncio.Queue()

        if process_id not in self._subscribers:
            self._subscribers[process_id] = []
        self._subscribers[process_id].append(queue)

        # Yield any existing historical events first
        for ev in self.get_events(process_id):
            yield {
                "event": ev.event_type,
                "data": json.dumps(ev.model_dump()),
            }

        end_time = asyncio.get_event_loop().time() + timeout_seconds
        try:
            while True:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=min(remaining, 2.0)
                    )
                    yield {
                        "event": event.event_type,
                        "data": json.dumps(event.model_dump()),
                    }
                    if event.event_type in (
                        TraceEventType.PROCESS_COMPLETED.value,
                        TraceEventType.ERROR.value,
                        "completed",
                        "failed",
                    ):
                        break
                except asyncio.TimeoutError:
                    continue
        finally:
            if (
                process_id in self._subscribers
                and queue in self._subscribers[process_id]
            ):
                self._subscribers[process_id].remove(queue)


default_tracer = WorkflowTracer()
global_tracer = default_tracer
