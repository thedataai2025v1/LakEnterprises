# Phase 12 — Infrastructure & Docker Design Evolution

## 1. Network & Component Wiring Evolution

In Phase 12, the system infrastructure evolved from a single backend service into a dual-service architecture comprising the Next.js Frontend Console and the FastAPI Backend Engine.

```mermaid
flowchart TB
    subgraph Host["Host Machine / Docker Network (lak-network)"]
        subgraph Browser["Operator Browser"]
            Client["Next.js Web Client\nhttp://localhost:3001"]
        end

        subgraph FrontendService["Frontend Container (lakenterprises-frontend)"]
            NextNode["Next.js 15 Server (:3001)\nNode.js Runtime"]
            NextRewrite["Next.js Internal Rewrites (/api/v1/*)"]
        end

        subgraph BackendService["Backend Container (lakenterprises-backend)"]
            Uvicorn["FastAPI / Uvicorn (:8001)\nPython 3.12 Runtime"]
            CORSHandler["CORSMiddleware (allow_origins: *)"]
        end

        subgraph DataStores["Enterprise Data Infrastructure"]
            Postgres[("PostgreSQL (:5432)")]
            Redis[("Redis (:6379)")]
            Qdrant[("Qdrant Vector (:6333)")]
        end
    end

    Client -->|HTTP 3001| NextNode
    NextNode --> NextRewrite
    NextRewrite -->|Proxy :8001| CORSHandler
    Client -.->|Direct API calls /api/v1/*| CORSHandler
    CORSHandler --> Uvicorn
    Uvicorn --> Postgres
    Uvicorn --> Redis
    Uvicorn --> Qdrant
```

---

## 2. Component Routing & Docker Details

### A. Port Allocations & Routing Scheme
| Service | Internal Port | Host Port | Protocol | Purpose |
|---|---|---|---|---|
| **Next.js Frontend** | 3001 | 3001 | HTTP | Operator Web Console & Dashboard |
| **FastAPI Backend** | 8001 | 8001 | HTTP | REST APIs, OpenAPI, LangGraph Engine |
| **PostgreSQL** | 5432 | 5432 | TCP | Relational Entities, Audit Logs, Checkpoints |
| **Redis** | 6379 | 6379 | TCP | Rate Limiting & Short-term Sessions |
| **Qdrant** | 6333 | 6333 | HTTP / gRPC | Vector Search & Chunk Embeddings |

### B. Request Routing Flow
1. **Direct Browser Request:** The operator accesses `http://localhost:3001`.
2. **Reverse Proxy / Rewrites:** `next.config.js` is configured to rewrite `/api/v1/:path*` to `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8001/api/v1/:path*`). This prevents Cross-Origin (CORS) complications during development and production container setups.
3. **Correlation Tracking:** The `LakApiClient` injects `X-Request-ID` into every HTTP header, which is captured by the backend's `AuditMiddleware` and correlated across logging outputs.
