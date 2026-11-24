# Phase 11 — Infrastructure & Component Wiring Evolution

## Overview: Infrastructure, Networking & Runtime Wiring

Phase 11 equips LakEnterprises with real-time operational governance. Infrastructure components must reliably handle long-lived process lifecycles where workflows pause for human sign-off, SLA timers count down independently of HTTP requests, and authorized state updates seamlessly resume worker executions across distributed services.

---

## 1. Component Topology & Service Boundaries

```mermaid
flowchart TB
    subgraph Client & Front-End Tier
        UI[Management Console / Next.js]
        MOBILE[Mobile Approver Webhook]
    end

    subgraph API Gateway & Ingress
        NGINX[Reverse Proxy / Ingress :80 / :443]
    end

    subgraph Application Tier
        APP[FastAPI LakEnterprises Service :8000]
        WF_API["/api/v1/workflow/*"]
        APPR_API["/api/v1/approvals/*"]
    end

    subgraph Orchestration & Tool Execution
        ENGINE[WorkflowEngine]
        GRAPH[LangGraph State Machine]
        EXECUTOR[ToolExecutor / RBAC Enforcer]
    end

    subgraph State, Memory & Persistence
        CP_STORE[(Workflow Checkpointer Store)]
        MEM_STORE[(Long-Term Memory / ChromaDB)]
        REDIS[(Redis Cache / SLA Task Queue)]
    end

    subgraph External Enterprise Systems
        CRM[(Enterprise CRM / Ticketing API)]
        ERP[(SAP / NetSuite Invoicing API)]
        EMAIL[SMTP / Slack Alerting Webhook]
    end

    UI & MOBILE --> NGINX
    NGINX --> APP
    APP --> WF_API & APPR_API
    WF_API & APPR_API --> ENGINE
    ENGINE --> GRAPH
    GRAPH --> CP_STORE
    GRAPH --> EXECUTOR
    EXECUTOR --> CRM & ERP
    ENGINE -.-> EMAIL
```

---

## 2. Dynamic Lifecycle: Pause, SLA Monitoring & Resume Wiring

The diagram below illustrates how an HTTP workflow run halts at the approval gate, persists state to disk/storage, triggers an SLA monitor, and unfreezes upon human review.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client / Intake Bot
    participant API as FastAPI Ingress
    participant Engine as WorkflowEngine
    participant Graph as LangGraph Runtime
    participant CP as WorkflowCheckpointer
    participant SLA as SLA / Timer Service
    actor Approver as Risk Officer (Human)
    participant Tool as ToolExecutor

    Client->>API: POST /api/v1/workflow/run
    API->>Engine: start(payload)
    Engine->>Graph: invoke(initial_state)
    Note over Graph: intake -> orchestrator -> investigation -> compliance -> escalation
    Graph->>Graph: human_approval_node() evaluates risk
    Graph->>CP: save_checkpoint(process_id, state)
    Graph->>SLA: register_deadline(process_id, deadline_iso)
    Graph-->>Engine: Halt (AWAITING_APPROVAL)
    Engine-->>API: 200 OK (status=AWAITING_APPROVAL, tier=TIER_4_EXECUTIVE)
    API-->>Client: Process paused; awaiting executive approval

    par Out-of-band SLA Tracking
        SLA->>API: GET /api/v1/workflow/{id}/sla
        API-->>SLA: {sla_breached: false, time_remaining: "0h 42m"}
    and Human Decision
        Approver->>API: POST /api/v1/workflow/{id}/decide (status=approved)
        API->>Engine: resume(process_id, updates)
    end

    Engine->>CP: load_checkpoint(process_id)
    CP-->>Engine: checkpoint_state
    Engine->>Graph: invoke(resumed_state)
    Note over Graph: human_approval_node -> execute_resolution_node
    Graph->>Tool: execute("crm_update_ticket", params)
    Tool-->>Graph: {ticket_id: "TCK-123", status: "resolved"}
    Graph->>Graph: finalize_node()
    Graph-->>Engine: Final State (COMPLETED)
    Engine-->>API: Resumed Execution Complete
    API-->>Approver: 200 OK (Process Completed, Ticket Resolved)
```

---

## 3. Docker & Container Network Isolation

To ensure maximum security and zero-trust boundaries:
1. **Tool Execution Isolation:** `ToolExecutor` validates RBAC user roles (`admin`, `manager`) prior to dispatching HTTP calls to external CRM/ERP APIs.
2. **Stateless App Scaling:** State is stored in serialized checkpoints, allowing any container replica in a Docker Swarm or Kubernetes cluster to service the `/decide` resume call.
3. **Resilient Failure Handling:** If a network failure occurs during tool execution, the node falls back to local simulation stubs while recording the detailed exception in the state audit history.
