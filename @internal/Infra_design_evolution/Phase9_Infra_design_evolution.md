# Phase 9 Infrastructure & Docker Design Evolution

## 1. Overview of Phase 9 Infrastructure
In Phase 9, the LakEnterprises system established the runtime infrastructure for executing specialist agents within the containerized backend. By standardizing input and output contracts into validated Pydantic models, each specialist agent operates as a decoupled micro-task runner that can execute locally, in background worker pools, or across future distributed agent clusters.

---

## 2. Docker Container Networking & Specialist Agent Wiring

```mermaid
flowchart TD
    subgraph External Network
        BrowserClient[Web Console / Analyst Browser :3001]
        CLIClient[CLI Runner: lakenterprises agent eval]
    end

    subgraph Docker Network: lak-enterprise-net
        Gateway[Nginx Ingress Reverse Proxy :80 / :443]

        subgraph FastAPI Core Application Container :8001
            MW[PIIScrubberMiddleware]
            
            subgraph Specialist Agent Subsystem Module
                Supervisor[SupervisorAgent: Task Planner]
                DocAnalyst[DocumentAnalysisAgent: Contract Reader]
                Compliance[ComplianceAgent: Policy Auditor]
                Knowledge[KnowledgeRetrievalAgent: Fact Retriever]
                Drafter[ResponseDraftingAgent: Memo Drafter]
                Escalation[EscalationHandoffAgent: Alert Router]
            end

            subgraph Agent Runtime Harness
                FakeLLM[FakeLLMHarness / Mock Provider: Offline Test Engine]
                LiveLLM[LangChain LLM Factory: OpenAI / Anthropic Provider]
            end

            subgraph Data & Tool Integrations
                ToolExec[ToolExecutor: ERP / CRM Adapters]
                MemServ[MemoryService: Short & Long Term Stores]
                GuardrailServ[PromptInjectionGuard & PIIScrubber]
            end
        end

        subgraph Core Persistence Containers
            Postgres[(PostgreSQL 16 DB :5432\naudit_log, processes, process_memory)]
            Redis[(Redis Session Cache :6379\nsession turns & variables)]
        end
    end

    BrowserClient -->|HTTPS| Gateway
    CLIClient -->|Internal Process| FastAPI
    Gateway --> MW
    MW --> Supervisor
    
    Supervisor --> DocAnalyst
    Supervisor --> Compliance
    Supervisor --> Knowledge
    Supervisor --> Drafter
    Supervisor --> Escalation

    DocAnalyst -.-> FakeLLM
    Compliance -.-> FakeLLM
    Knowledge -.-> MemServ
    Knowledge -.-> ToolExec
    Drafter -.-> GuardrailServ
    Escalation -.-> Postgres
    MemServ --> Redis
    MemServ --> Postgres
```

---

## 3. Specialist Agent Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Enterprise Process
    participant Sup as SupervisorAgent
    participant DA as DocumentAnalysisAgent
    participant Comp as ComplianceAgent
    participant KR as KnowledgeRetrievalAgent
    participant RD as ResponseDraftingAgent
    participant Esc as EscalationHandoffAgent

    User->>Sup: plan_workflow("Audit vendor contract & prepare approval")
    Sup-->>User: SupervisorPlan(subtasks=[DA, Comp, KR, RD, Esc])

    User->>DA: analyze_document(contract_text)
    DA-->>User: DocumentAnalysisResult(vendor="Acme", amount=$45,000)

    User->>Comp: check_compliance(policy="Procurement", amount=$45,000)
    Comp-->>User: ComplianceResult(is_compliant=True, risk_level="LOW")

    User->>KR: retrieve_knowledge("Acme SLA and discount history")
    KR-->>User: KnowledgeRetrievalResult(facts=[...], citations=["KB-PROC-01"])

    User->>RD: draft_response(purpose="Approval", citations=["KB-PROC-01"])
    RD-->>User: ResponseDraftResult(draft_text="Dear Partner...")

    User->>Esc: evaluate_escalation(description="Routine contract review", severity="LOW")
    Esc-->>User: EscalationHandoffResult(requires_human=False, severity="LOW")
```

---

## 4. Key Infrastructure & Reliability Policies
1. **Deterministic Test Isolation:** The `FakeLLMHarness` operates entirely in memory without requiring outbound network sockets, allowing tests and CLI commands (`lakenterprises agent eval`) to execute inside sandboxed or offline Docker build environments.
2. **Schema Boundary Enforcement:** All cross-agent communication is serialized into typed Pydantic models. A malformed response from an agent or LLM fails early at the agent boundary rather than corrupting database tables or downstream workflow graphs.
3. **Zero Network Latency in CI:** Benchmark evaluation scenarios run in $\le 1$ second across the entire suite, enabling rapid local development feedback and reliable continuous integration.
