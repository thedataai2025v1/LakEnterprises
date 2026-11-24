# Phase 13 — Infrastructure & Docker Design Evolution

## 1. Network & Component Wiring Evolution

In Phase 13, frontend-to-backend networking evolved to support real-time state polling, streaming trace telemetry, and asynchronous decision resumptions across the container network.

```mermaid
flowchart LR
    subgraph Host["Host Machine Network"]
        subgraph ClientBrowser["Client Browser (:3001)"]
            UI["Process Detail Screen (/processes/[id])"]
            Poller["State & SLA Poller (Every 3000ms)"]
            ActionTrigger["Decision Submitter (POST)"]
        end

        subgraph DockerBridge["Docker Network: lakenterprises-net"]
            subgraph Frontend["Frontend Container (:3001)"]
                NextApp["Next.js SSR / App Router"]
                Rewriter["Next.js Proxy Rewriter\n(/api/v1/* -> http://backend:8001/api/v1/*)"]
            end

            subgraph Backend["FastAPI Backend Container (:8001)"]
                FastAPIServer["Uvicorn / FastAPI Application"]
                AuditMiddleware["Audit & Correlation Middleware\n(Captures X-Request-ID)"]
                WorkflowRouter["/api/v1/workflow Router"]
            end

            subgraph Storage["Persistence Infrastructure"]
                CheckpointerStore[("Checkpointer Store\n(Redis / SQLite)")]
                TracerStore[("Trace Event Bus\n(InMemory / Redis)")]
            end
        end
    end

    UI --> Poller
    UI --> ActionTrigger
    Poller -->|GET /api/v1/workflow/{id}/state| Rewriter
    Poller -->|GET /api/v1/workflow/{id}/events| Rewriter
    ActionTrigger -->|POST /api/v1/workflow/{id}/decide| Rewriter

    Rewriter --> AuditMiddleware
    AuditMiddleware --> FastAPIServer
    FastAPIServer --> WorkflowRouter
    WorkflowRouter --> CheckpointerStore
    WorkflowRouter --> TracerStore
```

---

## 2. Component Routing & Docker Details

### A. Telemetry & Polling Optimization
| Route | Method | Polling Interval | Cache Policy | Purpose |
|---|---|---|---|---|
| `/api/v1/workflow/{id}/state` | `GET` | 3 seconds | `no-cache` | Fetches active node, status (`AWAITING_APPROVAL`, `COMPLETED`), and context |
| `/api/v1/workflow/{id}/events` | `GET` | 3 seconds | `no-cache` | Streams execution events with millisecond durations and payloads |
| `/api/v1/workflow/{id}/sla` | `GET` | 3 seconds | `no-cache` | Computes dynamic countdown, hours remaining, and breach flags |
| `/api/v1/workflow/{id}/decide` | `POST` | On-demand | N/A | Submits human approval, unfreezes checkpoint, resumes tool execution |

### B. Network Reliability & Performance Considerations
1. **Low-Overhead Polling:** The 3-second polling interval queries the in-memory or Redis checkpointer, avoiding heavy database joins or expensive re-evaluations.
2. **Reverse Proxy Transparency:** By rewriting `/api/v1/*` through `next.config.js`, browser security policies (same-origin policy) are satisfied without relying on open cross-origin wildcards in production.
3. **Trace Header Propagation:** Every polled request carries a unique `X-Request-ID` header, enabling exact correlation between browser console requests and backend server logs.
