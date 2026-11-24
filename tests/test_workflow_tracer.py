"""Unit tests for Phase 10 WorkflowTracer event streaming and telemetry."""

from __future__ import annotations

import asyncio

from lakenterprises.workflow.tracer import TraceEventType, WorkflowTracer


def test_tracer_emit_and_get_events() -> None:
    tracer = WorkflowTracer()
    proc_id = "proc-trace-01"

    ev1 = tracer.emit(
        process_id=proc_id,
        event_type=TraceEventType.PROCESS_STARTED,
        node_name="orchestrator",
        step_number=1,
        payload={"title": "Test Trace Process"},
    )
    assert ev1.process_id == proc_id
    assert ev1.event_type == TraceEventType.PROCESS_STARTED
    assert ev1.node_name == "orchestrator"
    assert ev1.step_number == 1

    _ = tracer.emit(
        process_id=proc_id,
        event_type=TraceEventType.NODE_COMPLETED,
        node_name="orchestrator",
        step_number=2,
        payload={"next": "document_analyst"},
    )

    history = tracer.get_events(proc_id)
    assert len(history) == 2
    assert history[0].step_number == 1
    assert history[1].step_number == 2


def test_tracer_filter_events() -> None:
    tracer = WorkflowTracer()
    proc_id = "proc-trace-02"

    tracer.emit(proc_id, TraceEventType.NODE_STARTED, node_name="node_a", step_number=1)
    tracer.emit(
        proc_id, TraceEventType.NODE_COMPLETED, node_name="node_a", step_number=2
    )
    tracer.emit(proc_id, TraceEventType.NODE_STARTED, node_name="node_b", step_number=3)

    started_events = tracer.get_events(proc_id, event_type=TraceEventType.NODE_STARTED)
    assert len(started_events) == 2

    node_a_events = tracer.get_events(proc_id, node_name="node_a")
    assert len(node_a_events) == 2


def test_tracer_stream_events() -> None:
    async def _async_test() -> None:
        tracer = WorkflowTracer()
        proc_id = "proc-trace-async"

        # Pre-populate event
        tracer.emit(proc_id, TraceEventType.PROCESS_STARTED, step_number=1)

        # Queue an event for async streaming
        loop = asyncio.get_event_loop()
        loop.call_soon(
            lambda: tracer.emit(
                proc_id,
                TraceEventType.PROCESS_COMPLETED,
                step_number=2,
                payload={"outcome": "Finished"},
            )
        )

        events_received: list[dict] = []
        async for sse_chunk in tracer.stream_events(proc_id):
            events_received.append(sse_chunk)
            if len(events_received) >= 2:
                break

        assert len(events_received) == 2
        assert events_received[0]["event"] == TraceEventType.PROCESS_STARTED.value
        assert events_received[1]["event"] == TraceEventType.PROCESS_COMPLETED.value

    asyncio.run(_async_test())


def test_tracer_clear() -> None:
    tracer = WorkflowTracer()
    proc_id = "proc-clear-test"
    tracer.emit(proc_id, TraceEventType.PROCESS_STARTED, step_number=1)
    assert len(tracer.get_events(proc_id)) == 1

    tracer.clear(proc_id)
    assert len(tracer.get_events(proc_id)) == 0
