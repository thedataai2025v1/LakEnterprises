# Phase 10 Infrastructure & Docker Design Evolution

## 1. Overview of Phase 10 Infrastructure
Phase 10 deploys the **LangGraph StateGraph runtime, in-memory checkpointer, and streaming telemetry bus** into the LakEnterprises containerized backend. This infrastructure provides thread-isolated execution, persistent checkpoint snapshots, and real-time Server-Sent Events (SSE) connections between the FastAPI server and web clients.

---

## 2. Docker Container Networking & Workflow Graph Wiring

```mermaid
flowchart TD
    subgraph External Clients
        WebClient[Web Browser / Analyst Dashboard :3001]
        CLIClient[CLI Runner: lakenterprises workflow run]
    end

    subgraph Docker Network: lak-enterprise-net
        Gateway[Nginx Ingress Reverse Proxy :80 / :443]

        subgraph FastAPI Core Application Container :8001
            AuditMW[AuditMiddleware & PIIScrubber]
            WorkflowRouter[/api/v1/workflow Router]

            subgraph LangGraph StateGraph Execution Engine
                CompiledGraph[Compiled StateGraph: LangGraph 0.2+]
                StateCheckpointer[ProcessStateCheckpointer]
                LangGraphMemory[LangGraph MemorySaver / Thread Store]
            end

            subgraph Specialist Agent Registry
                SupervisorAgent[SupervisorAgent]
                DocAnalystAgent[DocumentAnalysisAgent]
                ComplianceAgent[ComplianceAgent]
                KnowledgeAgent[KnowledgeRetrievalAgent]
                DrafterAgent[ResponseDraftingAgent]
                EscalationAgent[EscalationHandoffAgent]
            end

            subgraph Telemetry & Event Streaming
                WorkflowTracer[WorkflowTracer Event Bus]
                AsyncQueues[Async Subscriber Queues: SSE / Streaming]
            end
        end

        subgraph Core Persistence Services
            Postgres[(PostgreSQL 16 DB :5432\naudit_log, processes, memory)]
            Redis[(Redis Session Cache :6379\nrate limiting, session locks)]
        end
    end

    WebClient -->|HTTP / SSE| Gateway
    CLIClient -->|CLI Commands| WorkflowRouter
    Gateway -->|Reverse Proxy /api/v1/workflow| WorkflowRouter
    WorkflowRouter --> WorkflowEngine
    WorkflowEngine --> CompiledGraph

    CompiledGraph <--> LangGraphMemory
    CompiledGraph --> StateCheckpointer
    CompiledGraph -.-> Specialist Agent Registry
    WorkflowEngine -.->|Telemetry Events| WorkflowTracer
    WorkflowTracer --> AsyncQueues
    AsyncQueues -->|SSE Chunks| Gateway
```

---

## 3. Infrastructure & Component Interaction

### A. Thread-Isolated State Persistence
- **LangGraph Checkpointer Isolation:** Every workflow run receives a unique `configurable: {"thread_id": process_id}`. This isolates the execution state of concurrent customer processes in memory.
- **Process State Checkpoint Store:** In addition to LangGraph's internal serialized state graph, `ProcessStateCheckpointer` maintains an auditable sequence of snapshots with human-readable timestamps and step indices.

### B. Streaming Telemetry Infrastructure (SSE)
- When a client connects to `GET /api/v1/workflow/{process_id}/events/stream`, FastAPI opens a persistent HTTP connection using `StreamingResponse(media_type="text/event-stream")`.
- `WorkflowTracer` registers an `asyncio.Queue` for that connection, instantly streaming all prior historical events and publishing live node transition events as they occur.

### C. Resource & Concurrency Profile
- **Memory Footprint:** Each in-flight process maintains a lightweight `WorkflowState` dictionary (~15-30 KB), enabling hundreds of concurrent workflow threads inside the single FastAPI worker container.
- **Zero-Block Execution:** Asynchronous event queues decouple the execution graph from the client connection, ensuring network latency or disconnected clients cannot stall the multi-agent graph.
