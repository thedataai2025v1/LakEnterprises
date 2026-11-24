# Phase 13 — Project System Design Evolution

## 1. Simple Initial Design (Start of Phase 13)

At the beginning of Phase 13, the frontend had a general shell with list pages (`/processes`, `/approvals`), but opening a specific process had no dedicated workflow interaction screen. Workflow execution and pause gates were inspectable only through CLI logs or raw JSON API endpoints:

```mermaid
flowchart LR
    subgraph Frontend["Console UI Shell (Phase 12)"]
        Dashboard["Dashboard (/)"]
        ProcList["Processes Table (/processes)"]
        RawAPI["No Dedicated Workflow Screen"]
    end

    subgraph Backend["FastAPI Backend (:8001)"]
        WfRoutes["/api/v1/workflow/:id/*"]
        Checkpointer["State Checkpointer (Redis / SQLite)"]
        LangGraph["13-Node StateGraph"]
    end

    Dashboard --> ProcList
    ProcList -.->|Raw JSON only| WfRoutes
    WfRoutes --> Checkpointer
    WfRoutes --> LangGraph
```

### Limitations:
- Operators could not see which node of the 13-node graph was running.
- No live polling or timeline of step durations.
- Human approval decisions required raw curl POSTs to `/api/v1/workflow/{id}/decide`.

---

## 2. Advanced Evolved System Design (End of Phase 13)

By the end of Phase 13, LakEnterprises features an interactive, real-time Process Workflow Screen at `/processes/[id]` with automated polling, telemetry stream, step visualization, and approval decision controls:

```mermaid
flowchart TB
    subgraph BrowserSpace["Operator Browser (:3001)"]
        subgraph Screen["/processes/[id] Screen"]
            Header["Breadcrumbs & Live Polling Toggle (3s)"]
            
            subgraph Layout["Split Workflow Layout"]
                subgraph LeftCol["Left: Graph Engine Stepper"]
                    StepsPanel["WorkflowStepsPanel\n- 13 Canonical Nodes\n- Status: Passed / Executing / Awaiting\n- SLA Metrics & Time Remaining"]
                    ContextCard["Workflow Context JSON"]
                end
                
                subgraph RightCol["Right: Governance & Telemetry"]
                    ActionsBar["ProcessActions\n- Dispute Exposure & Risk Level\n- RBAC Enforcement\n- Decision Modal (Approve / Reject / Escalate)"]
                    Timeline["ProcessTimeline\n- Event Stream (START, END, ERROR)\n- Execution Duration (ms)\n- Step Payloads & Locator Links"]
                end
            end
        end
        
        ApiClient["LakApiClient\n- getWorkflowState()\n- getWorkflowEvents()\n- getWorkflowSLA()\n- decideWorkflowApproval()"]
    end

    subgraph BackendSpace["FastAPI Backend Engine (:8001)"]
        subgraph WorkflowAPI["Workflow Endpoints"]
            GetState["GET /api/v1/workflow/{id}/state"]
            GetEvents["GET /api/v1/workflow/{id}/events"]
            GetSLA["GET /api/v1/workflow/{id}/sla"]
            PostDecide["POST /api/v1/workflow/{id}/decide"]
        end
        
        subgraph Runtime["LangGraph State Engine"]
            Checkpointer["Thread Checkpointer"]
            Tracer["WorkflowTracer Event Bus"]
            Router["EscalationRouter & SLA Timer"]
            Resolution["execute_resolution_node (ToolExecutor)"]
        end
    end

    Header --> Layout
    StepsPanel --> ApiClient
    ActionsBar --> ApiClient
    Timeline --> ApiClient
    
    ApiClient -->|Polling 3s| GetState
    ApiClient -->|Polling 3s| GetEvents
    ApiClient -->|Polling 3s| GetSLA
    ApiClient -->|On Decision| PostDecide
    
    GetState --> Checkpointer
    GetEvents --> Tracer
    GetSLA --> Router
    PostDecide --> Checkpointer
    PostDecide --> Resolution
```

---

## 3. Subtask Evolutionary Progression

### Subtask P13-1: Process Detail and Timeline Layout
- Created Next.js dynamic route `frontend/src/app/processes/[id]/page.tsx`.
- Designed the master screen header with breadcrumbs, status pill, and 3-column responsive grid layout.
- Implemented `ProcessTimeline` displaying recorded chronological trace events, duration metrics, and node payloads.

### Subtask P13-2: Workflow Steps Panel with Polling
- Implemented `WorkflowStepsPanel` mapping out the canonical 13-node LangGraph execution sequence.
- Wired automated 3-second polling interval with pause/resume toggle for non-intrusive monitoring.
- Incorporated SLA countdown cards tracking tier limits, elapsed time, and breach warnings.

### Subtask P13-3: Approve, Reject, and Escalate Actions UI
- Implemented `ProcessActions` featuring real-time risk summaries and dispute exposure badges.
- Built interactive confirmation modals capturing operator justification notes.
- Integrated RBAC permission gating ensuring only authorized roles (`analyst`, `admin`) can submit approval decisions.

### Subtask P13-4: Frontend Integration Tests
- Created Node.js unit tests in `frontend/tests/workflow-screen.test.js` validating client method signatures.
- Implemented comprehensive FastAPI backend integration tests in `tests/test_frontend_workflow_screen.py` verifying the full workflow run, state query, events stream, SLA metrics, and approval decision cycle.
