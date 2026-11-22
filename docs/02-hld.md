# 02 – High-Level Design

## What are we building?

The architecture: a Next.js research UI, a FastAPI backend, a LangGraph research workflow, and **four**
data stores (relational, vector, graph, cache) behind replaceable interfaces.

## Why?

The interesting design decision in this project is not "which framework" but **which store answers which
part of a question**. Everything else exists to make that decision explicit, inspectable and testable.

## Which concept does it teach?

Polyglot persistence with one orchestrator. Also: how to keep three storage technologies from leaking
into agent code (protocols), and how a long-running AI workflow fits into a normal HTTP request/response
API (202 + background task + polling).

---

## 1. System context

```text
                          ┌──────────────────────────────┐
                          │  Analyst (browser, :3001)    │
                          └──────────────┬───────────────┘
                                         │  JWT (demo login or Supabase)
                          ┌──────────────▼───────────────┐
                          │  Next.js 15 frontend         │
                          │  /search /research/[id]      │
                          │  /knowledge-graph /documents │
                          └──────────────┬───────────────┘
                                         │  REST /api/v1, X-Request-ID
                          ┌──────────────▼───────────────┐
                          │  FastAPI backend (:8001)     │
                          │  routers · services · repos  │
                          │  middleware: req-id, rate    │
                          │             limit, audit     │
                          └──────┬────────────┬──────────┘
                                 │            │
              ┌──────────────────▼───┐   ┌────▼─────────────────────────┐
              │ LangGraph research   │   │ Read paths (browse pages)    │
              │ workflow (13 nodes)  │   │ customers/incidents/decisions│
              └──────┬───────┬───────┘   └──────────────────────────────┘
                     │       │
    ┌────────────────▼┐ ┌────▼───────────┐ ┌──────────────┐ ┌──────────────┐
    │ PostgreSQL /    │ │ Qdrant /       │ │ Neo4j /      │ │ Redis /      │
    │ SQLite          │ │ in-memory      │ │ in-memory    │ │ fakeredis    │
    │ records, chunks,│ │ chunk vectors  │ │ entities +   │ │ cache, conv. │
    │ sessions, audit │ │                │ │ relationships│ │ memory, rate │
    └─────────────────┘ └────────────────┘ └──────────────┘ └──────────────┘
                     │
              ┌──────▼──────────────────────┐
              │ LLM provider (any of 8) via │
              │ get_llm() / embeddings      │
              └─────────────────────────────┘
```

Supabase (Postgres + Auth + Storage + RLS) is the managed production form of the relational box.
Qdrant Cloud and Neo4j Aura are the managed forms of the vector and graph boxes.

## 2. Request flow for one research question

```text
POST /api/v1/research  { question }
  │
  ├─ validate (Pydantic: 5..2000 chars)                backend/app/api/research.py
  ├─ create research_sessions row                      services/research_service.create_session
  ├─ schedule BackgroundTask ─────────────┐            → responds 202 {session_id, status:"running"}
  │                                       │
  │                                       ▼
  │                        agents/graph.py  StateGraph(ResearchState)
  │                        13 nodes, each wrapped in tracer.node(...)
  │                        state persisted after every node (services/research_service._persist)
  │                        every transition written to workflow_events
  │
GET /api/v1/research/{id}     ← frontend polls every 2 s
GET /api/v1/research/{id}/events
```

The frontend never waits on a long request. The state in the database *is* the progress bar.

## 3. Component responsibilities

| Layer | Folder | Responsibility | Must not |
|---|---|---|---|
| API | `backend/app/api/` | HTTP shape, auth, validation, status codes | contain business logic |
| Services | `backend/app/services/` | orchestrate: run the graph, persist state, handle approvals, seed | know about HTTP |
| Repositories | `backend/app/repositories/` | all SQL via SQLAlchemy | be imported by agents directly |
| Core | `backend/app/core/` | config, llm, db, redis, security, logging, guardrails, observability | import from `agents/` (cycle) |
| Agents | `agents/` | the graph, nodes, specialists, deterministic rules | talk to HTTP or the browser |
| RAG | `rag/` | parsing, chunking, extraction, vector store, graph store, retrievers, SQL retrieval | know about FastAPI |
| Memory | `memory/` | the four memory scopes | be mixed with retrieval |
| Integrations | `integrations/` | protocols + mock adapters + MCP server | be required for the demo |

Import direction is one-way: `api → services → repositories → models`, and `agents/rag/memory → app.core`.

## 4. The three retrieval paths

```text
                    ┌──────────────────────┐
   sub-question ───▶│  route_retrieval     │
                    └───┬──────┬───────┬───┘
        vector/hybrid   │      │ sql   │ graph
                        ▼      ▼       ▼
        ┌───────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
        │ rag/retriever.py  │ │rag/sql_retrieval│ │ rag/graph_store.py   │
        │ semantic + BM25   │ │ validate_sql()  │ │ typed traversals     │
        │ + RRF + rerank    │ │ + templates     │ │ + Cypher templates   │
        └─────────┬─────────┘ └────────┬────────┘ └──────────┬───────────┘
                  └────────────────────┴─────────────────────┘
                                       ▼
                             collect_evidence  (merge + dedupe + id)
```

All three produce the **same** `Evidence` shape (`backend/app/schemas/common.py`), differing only in
`source_type` (`document` / `sql` / `graph`) and `locator`. That is what makes one citation list possible.

## 5. Key design decisions

| Decision | Alternative | Why this one |
|---|---|---|
| Retrieval strategy chosen at run time by a router node | one fixed retriever | the canonical question needs three at once |
| Deterministic `agents/rules.py` on top of LLM output | trust the model | the demo must work with `LLM_PROVIDER=fake` and rules stop a relationship question being sent to vector-only |
| In-memory implementations of both vector and graph stores | require Docker | `make test` and `make demo` run with zero services |
| Typed graph traversals that *also* return their Cypher | free-form generated Cypher | safe by construction, and students still see the query |
| SQL templates + a validator, LLM generation only as an addition | free-form generated SQL | injection and destructive statements become impossible, not unlikely |
| Bounded corrective loop (`MAX_CORRECTIVE_ROUNDS=1`) | retry until satisfied | agent loops must terminate |
| Evidence and citation verification as separate nodes | one "check the answer" step | you can point at each guarantee and test it alone |

## Files to open

- `backend/app/main.py` – app factory and lifespan (creates tables, seeds, builds the graph, ingests documents)
- `agents/graph.py` – `GRAPH_NODES`, `GRAPH_EDGES`, `build_graph()`
- `backend/app/services/research_service.py` – `create_session`, `start_research`, `_persist`
- `rag/vector_store.py`, `rag/graph_store.py` – the two replaceable protocols
- `docs/API_CONTRACT.md`

## Command to run

```bash
make backend          # :8001
curl -s localhost:8001/health/ready | python -m json.tool
```

## What students should observe

Under Docker Compose (real services) `/health/ready` names the actual backing stores:

```json
{
    "status": "ready",
    "checks": {
        "database":     {"status": "ok", "detail": "sqlite"},
        "redis":        {"status": "ok", "detail": "real"},
        "vector_store": {"status": "ok", "detail": "qdrant http://qdrant:6333"},
        "graph_store":  {"status": "ok", "detail": "neo4j bolt://neo4j:7687"},
        "llm":          {"status": "ok", "detail": {"llm_provider": "fake", "...": "..."}}
    }
}
```

Run it locally without Docker and the same endpoint reports
`"memory (70 chunks)"` and `"memory (85 nodes, 260 edges)"`. **Same code, different adapters** – that is
the whole point of the protocols.

## Modification students can try

Start the backend with `GRAPH_STORE=neo4j` while Neo4j is *not* running. `/health/ready` becomes
`degraded` with an error detail for `graph_store`, and the graph sub-questions record an error instead of
crashing the workflow. Compare with `GRAPH_STORE=memory`.

## Common errors

- Importing `agents.*` from `app.core.*` → circular import. Core is the bottom layer.
- Calling the graph directly from a router (blocking the request) instead of scheduling a background task.
- Two servers on port 8001 (a container and a local `uvicorn`) answering different results; check `docker ps`.

## Production extension

Move the graph execution out of the web process into a worker (Celery / Cloud Tasks / SQS consumer)
reading the same `research_sessions` table, and switch the checkpointer to
`langgraph-checkpoint-postgres` so any worker can resume any run.
