# Phase 12 — Project System Design Evolution

## 1. Simple Initial Design (Start of Phase 12)

Prior to Phase 12, LakEnterprises existed purely as a headless backend API and CLI tool. Client interaction occurred solely through direct HTTP calls (via curl, Postman, or integration scripts) or local terminal commands:

```mermaid
flowchart LR
    subgraph Client["Direct Client Access"]
        CLI["CLI Tool (Terminal)"]
        Curl["HTTP / curl / Scripts"]
    end

    subgraph Backend["FastAPI Core Engine (:8001)"]
        Router["API Routers"]
        Auth["JWT & RBAC Middleware"]
        Graph["LangGraph Workflow Engine"]
        Storage[("PostgreSQL / Redis / Qdrant")]
    end

    CLI --> Router
    Curl --> Router
    Router --> Auth
    Auth --> Graph
    Graph --> Storage
```

### Limitations of Initial Design:
- **No Human-Friendly UI:** Business stakeholders and operations teams could not visually track workflow progress or inspect agent states.
- **Manual Decision Submissions:** Approving or rejecting high-dollar disputes required manual HTTP POST payloads.
- **Static Verification:** Testing RBAC required generating and pasting JWT tokens into header parameters manually.

---

## 2. Advanced Evolved System Design (End of Phase 12)

With Phase 12 complete, LakEnterprises features a dedicated, modern Next.js 15 Console UI shell running on port 3001, communicating with the FastAPI backend through a typed API client:

```mermaid
flowchart TB
    subgraph UserSpace["Browser & Operator Interface (:3001)"]
        UI["Next.js 15 App Shell (React 19 + Tailwind)"]
        Nav["Sidebar & Header Shell"]
        AuthCtx["AuthProvider & Session State"]
        
        subgraph Views["Console Views"]
            DashView["Dashboard (/)\n(Active KPIs & Summaries)"]
            ProcView["Processes (/processes)\n(Instance & Template Status)"]
            ApprView["Approvals (/approvals)\n(Human-in-the-Loop Queue)"]
            DocView["Knowledge (/documents)\n(Hybrid Search & Corpora)"]
            LoginView["Demo Login (/login)\n(RBAC Persona Switching)"]
        end
        
        ApiClient["LakApiClient (TypeScript)\n- Automatic Bearer JWT Injection\n- Correlation X-Request-ID\n- Typed DTO Contracts"]
    end

    subgraph BackendSpace["FastAPI Backend (:8001)"]
        Cors["CORS & Request-ID Middleware"]
        AuthMid["Audit & Rate Limit Middleware"]
        
        subgraph Endpoints["Backend Endpoints"]
            AuthRoutes["/api/v1/auth/*"]
            ProcRoutes["/api/v1/processes/*"]
            ApprRoutes["/api/v1/approvals/*"]
            DocRoutes["/api/v1/documents/*"]
            WfRoutes["/api/v1/workflow/*"]
        end
        
        Engine["LangGraph 13-Node Workflow Engine"]
    end

    UI --> Nav
    Nav --> Views
    Views --> AuthCtx
    AuthCtx --> ApiClient
    ApiClient -- "HTTP REST (JSON)" --> Cors
    Cors --> AuthMid
    AuthMid --> Endpoints
    Endpoints --> Engine
```

---

## 3. Subtask Evolutionary Progression

### Subtask P12-1: App Shell and Navigation Frame
- Scaffolded Next.js 15 workspace with Tailwind CSS and responsive layout.
- Established persistent `Sidebar` and `Navbar` showing service health and identity state.

### Subtask P12-2: Strongly Typed API Client
- Implemented `LakApiClient` wrapping standard fetch with Bearer token persistence in localStorage.
- Integrated correlation tracking via `X-Request-ID` header generation on every outgoing client request.

### Subtask P12-3: RBAC Layout & Session Management
- Created `AuthProvider` context managing active tokens, user profiles, and permission predicates (`hasRole`).
- Built dedicated `/login` page enabling 1-click persona switching (Viewer, Analyst, Administrator) for live RBAC validation.

### Subtask P12-4: Dashboard & Resource List Views
- Built comprehensive `/` overview dashboard with metric cards and recent activity tables.
- Built `/processes`, `/approvals`, and `/documents` pages for managing enterprise workflows, approving disputes, and conducting hybrid vector search.
