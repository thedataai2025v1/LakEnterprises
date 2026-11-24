# Phase 11 — Project System Design Evolution

## Overview & Architectural Goals

Phase 11 introduces **Human-in-the-Loop (HITL) runtime orchestration, dynamic tiered escalation routing, deterministic SLA tracking, and authorized resolution execution**.

Prior to Phase 11, Phase 10 established the foundation of a compiled LangGraph state graph with checkpointers and tracing, but executions proceeded strictly non-interactively from document intake to final response drafting. Phase 11 bridges the gap between autonomous AI synthesis and enterprise risk governance by providing resilient pause/resume barriers and transactional tool resolution.

---

## Evolution Stages: Simple to Advanced

### Stage 1: Initial Linear Execution (Phase 10 Baseline)

In the Phase 10 baseline, the graph traversed straight from `intake` through `compliance` to `response_drafter` and `finalize`. If a compliance violation occurred, the process merely set status flags but did not pause for human intervention.

```mermaid
flowchart LR
    A[intake] --> B[orchestrator]
    B --> C[doc_investigation]
    C --> D[compliance]
    D --> E[response_drafter]
    E --> F[finalize]
```

---

### Stage 2: Introducing the Human Approval Interrupt Gate (P11-1)

To protect corporate capital and adhere to compliance boundaries, we introduce `human_approval_node` and conditional routing after `escalation_node`. When `approval_required == True`, the node halts execution and freezes the state in the `WorkflowCheckpointer`.

```mermaid
flowchart TD
    subgraph Autonomous Analysis
        A[intake] --> B[orchestrator]
        B --> C[investigate]
        C --> D[compliance]
        D --> E[drafter]
        E --> F[escalation]
    end

    F --> G{Requires Approval?}
    G -- No --> H[finalize]
    G -- Yes (Pending) --> I[human_approval_node]
    I --> J((Halt / Save Checkpoint))
```

---

### Stage 3: Tiered Escalation Routing & Dynamic SLA Calculation (P11-3)

High-value transactions cannot simply sit in a single generic queue. We integrated `EscalationRouter` to inspect dollar exposure and assign corporate hierarchy tiers and SLA deadlines:

```mermaid
flowchart TD
    A[Dispute Amount Evaluated] --> B{Amount Threshold}
    B -- "<= $1,000" --> C[Tier 1: Analyst / 24h SLA]
    B -- "$1,001 - $10,000" --> D[Tier 2: Manager / 8h SLA]
    B -- "$10,001 - $50,000" --> E[Tier 3: Director / 4h SLA]
    B -- "> $50,000" --> F[Tier 4: Executive / 1h SLA]

    C & D & E & F --> G[Compute ISO Deadline & SLA Status]
```

---

### Stage 4: Advanced End-to-End Runtime with Authorized Tool Execution (P11-2, P11-4, P11-5)

The complete Phase 11 architecture links external management APIs, persistent checkpoint restoration, and shared tool execution paths for automated resolution.

```mermaid
flowchart TD
    subgraph Autonomous Processing
        N1[intake_node] --> N2[orchestrator_node]
        N2 --> N3[document_investigation_node]
        N3 --> N4[compliance_node]
        N4 --> N5[response_drafter_node]
        N5 --> N6[escalation_node]
    end

    subgraph Governance & Interrupt
        N6 --> C1{route_after_escalation}
        C1 -- "approval_required && pending" --> N7[human_approval_node]
        N7 --> P1((PAUSED: awaiting_approval))
    end

    subgraph Human Decision & Resume API
        P1 -.->|Out-of-band review| API["POST /api/v1/workflow/{id}/decide"]
        API --> ENGINE[WorkflowEngine.resume]
        ENGINE --> N7
    end

    subgraph Resolution Execution
        N7 --> C2{route_after_approval}
        C2 -- "approved" --> N8[execute_resolution_node]
        C2 -- "rejected" --> N9[finalize_node]
        N8 --> T1[ToolExecutor: crm_update_ticket]
        T1 --> N9
        C1 -- "not required" --> N8
    end

    subgraph Telemetry & Audit
        N1 & N7 & N8 & N9 -.-> TRACER[(WorkflowTracer & Checkpointer)]
    end
```

---

## Key Design Decisions & Trade-Offs

1. **State Immobility via Checkpoints vs. Active Long-Polling:**
   - *Decision:* Halt the graph completely and store state in SQLite/memory rather than keeping worker threads sleeping or waiting.
   - *Rationale:* Web servers and worker processes scale horizontally without holding persistent thread locks or socket connections open during multi-hour or multi-day human reviews.
2. **Idempotent Node Re-Entry:**
   - *Decision:* `escalation_node` checks `approval_status`: if already `"approved"` or `"rejected"`, it does not overwrite the status back to `"pending"`.
   - *Rationale:* Ensures that resuming a workflow from the beginning or from intermediate checkpoints does not wipe out human-provided decisions.
3. **Unified Tool Execution Path (`execute_resolution_node`):**
   - *Decision:* Reuse Phase 6 `ToolExecutor` (`crm_update_ticket`, `db_read_records`) for workflow resolutions.
   - *Rationale:* Guarantees role-based access control (RBAC), tool argument validation, and audit logging remain identical across conversational agents and workflow engines.
