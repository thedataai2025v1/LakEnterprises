# CLAUDE.md – NovaEnterprise Knowledge & Decision Intelligence Platform

This file is the operating guide for anyone (human or Claude) working in this repository. It distils
`00-problem.md`, `01-prd.md` and `02-hld.md`. When this file and those specs disagree, the specs win:
fix this file.

> **Status:** spec-first. The repo currently holds only the design docs. The paths below describe the
> target layout; create them as described rather than inventing new ones.

---

## 1. What this system is

An enterprise research platform for the fictional company **NovaEnterprise**. An analyst asks one
natural-language question and gets a **cited, verified answer** assembled from documents, database
records and a knowledge graph, with every retrieval step open to inspection.

```text
Vector RAG  +  Graph RAG  +  SQL  +  Agents  +  Memory
```

**Core idea:** choosing a retrieval strategy is a routing decision the system makes at run time for each
sub-question. It is not a choice of library. Never hard-code a single retriever.

### The canonical question (every change must keep it working)

> Which customers were impacted by the Payments API last quarter, what incidents occurred,
> which teams own those services, and what decisions were taken to prevent recurrence?

| Sub-question | Strategy | Source |
|---|---|---|
| sq1 which customers were impacted | `graph` | `(Service)<-[:AFFECTED]-(Incident)-[:IMPACTED]->(Customer)` |
| sq2 what incidents occurred | `sql` | `incidents JOIN services`, filtered by date |
| sq3 which teams own those services | `graph` | `(Service)-[:OWNED_BY]->(Team)` |
| sq4 what decisions prevent recurrence | `hybrid` | postmortems + ADRs (+ graph) |

Expected `make demo` output: complexity `complex`, entity `Payments API`, time range `last quarter`,
4 sub-questions, 1 SQL query, 3 Cypher traversals, 9 evidence items, a verification ratio, and a cited
answer. `strategies_used` = `graph, sql, vector`, corrective rounds `0`.

A **simple** question (e.g. "What is our data retention policy?") must produce complexity `simple`,
one sub-question, no SQL, no Cypher, and `strategies_used == [vector]`.

---

## 2. Architecture

```text
Next.js 15 UI (:3001) ──JWT──▶ FastAPI (:8001) ──▶ LangGraph workflow (13 nodes)
                                       │                 │
                                       ▼                 ▼
          PostgreSQL/SQLite · Qdrant/in-memory · Neo4j/in-memory · Redis/fakeredis
                                       │
                                 LLM via get_llm() / get_embedding_model()  (8 providers)
```

| Store | Holds | Offline adapter | Production adapter |
|---|---|---|---|
| Relational | records, chunks, research sessions, workflow events, audit | SQLite | PostgreSQL / Supabase |
| Vector | chunk embeddings | `VECTOR_STORE=memory` | Qdrant / Qdrant Cloud |
| Graph | entities and relationships | `GRAPH_STORE=memory` | Neo4j / Aura |
| Cache | cache, conversation memory, rate limit buckets | fakeredis | Redis |

### Request lifecycle

1. `POST /api/v1/research {question}`. Pydantic validates 5..2000 chars.
2. `research_service.create_session` writes a `research_sessions` row.
3. A `BackgroundTask` runs `agents/graph.py`. The endpoint returns **202** `{session_id, status:"running"}` immediately.
4. Each node is wrapped in `tracer.node(...)`. State is persisted after every node (`_persist`) and every transition goes to `workflow_events`.
5. The frontend polls `GET /api/v1/research/{id}` and `/events` every 2 s. **The DB state is the progress bar.**

Never run the graph inside the request handler.

### Repository layout and layer rules

| Folder | Owns | Must NOT |
|---|---|---|
| `backend/app/api/` | HTTP shape, auth, validation, status codes | contain business logic |
| `backend/app/services/` | orchestration: run graph, persist, approvals, seeding | know about HTTP |
| `backend/app/repositories/` | all SQL via SQLAlchemy | be imported by `agents/` |
| `backend/app/core/` | config, llm, db, redis, security, logging, guardrails, observability | import from `agents/` (causes a cycle) |
| `backend/app/schemas/` | Pydantic models, incl. `Evidence` in `common.py` | – |
| `agents/` | graph, nodes (`agents/nodes/`), specialists (`SQLAgent`, `GraphAgent`), `rules.py` | touch HTTP or the browser |
| `rag/` | parsing, chunking, extraction, `vector_store.py`, `graph_store.py`, `retriever.py`, `sql_retrieval.py`, `ingest.py` | know about FastAPI |
| `memory/` | the four memory scopes (`memory_service.py`) | be mixed with retrieval |
| `integrations/` | `protocols.py` (`DocumentSource`), mock adapters, MCP server | be required for the demo |
| `frontend/` | Next.js: `/search`, `/research/[id]`, `/knowledge-graph`, `/documents` | – |
| `sample_data/` | seed JSON + `documents/*.md` | – |
| `tests/` | `unit/`, `api/`, `rag/`, `evaluation/` | – |
| `docs/` | `API_CONTRACT.md`, `FRONTEND_ASSUMPTIONS.md` | – |

Imports go one way only: `api → services → repositories → models`, and `agents / rag / memory → app.core`.

---

## 3. The research workflow

`agents/graph.py` defines `GRAPH_NODES`, `GRAPH_EDGES` and `build_graph()` over `StateGraph(ResearchState)`.
`GRAPH_NODES` is the source of truth for the 13 nodes. The nodes the specs name:

| Node | File | Job |
|---|---|---|
| analyze_query | `agents/nodes/analyze_query.py` | intent, entities, time range, needs_relationships, needs_aggregation |
| assess_complexity | `agents/nodes/assess_complexity.py` | `simple / moderate / complex` |
| decompose | `agents/nodes/decompose.py` | ≤ `MAX_SUBQUESTIONS` (default 4) sub-questions |
| route_retrieval | `agents/nodes/route_retrieval.py` | one of `vector / sql / graph / hybrid` per sub-question |
| retrieval | `rag/retriever.py`, `rag/sql_retrieval.py`, `rag/graph_store.py` | run the chosen strategy |
| collect_evidence | – | merge, dedupe and assign ids |
| check_missing_evidence | `agents/nodes/check_missing_evidence.py` | find unanswered parts |
| corrective_retrieval | `agents/nodes/corrective_retrieval.py` | at most `MAX_CORRECTIVE_ROUNDS` (default 1) |
| verify_evidence | `agents/nodes/verify_evidence.py` | check each claim against the evidence |
| synthesize_answer | `agents/nodes/synthesize_answer.py` | answer with `[n]` citation markers |
| verify_citations | `agents/nodes/verify_citations.py` | every `[n]` resolves; report invalid ones |

`agents/rules.py` holds the **deterministic** analysis, decomposition and routing rules. They are applied
on top of LLM output so the system works with `LLM_PROVIDER=fake` and so a relationship question can
never be routed to vector-only retrieval. Do not delete or bypass them in favour of "trust the model".

### One evidence shape

Every retriever returns the same `Evidence` model (`backend/app/schemas/common.py`). Items differ only
in `source_type` (`document | sql | graph`) and `locator`. This is what lets one citation list cover all
three stores. Do not add retriever-specific evidence types.

---

## 4. Non-negotiable invariants

Do not break these. Each one has a test.

1. **Offline-first.** `make test` and `make demo` run with no API key and no external service:
   `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`, SQLite, fakeredis.
2. **Read-only data access.** All SQL goes through `validate_sql()` plus templates, restricted to an
   allowlisted schema. LLM-generated SQL is only an addition and must also pass the validator. Graph
   access goes through **typed traversals** that also return their Cypher. Do not run free-form
   generated Cypher.
3. **Bounded loops.** The corrective loop stops after `MAX_CORRECTIVE_ROUNDS`. Agent loops must always
   end.
4. **Untrusted content is data, never instructions.** `sample_data/documents/vendor-note-processor-update.md`
   contains a deliberate prompt injection. It must be indexed, wrapped, scanned and **flagged**
   (`backend/app/core/guardrails.py`), and never obeyed.
5. **Verification before shipping.** Evidence verification and citation verification are two separate
   nodes. Do not merge them.
6. **Replaceable stores.** Agent code talks only to the `VectorStoreService` / `GraphStoreService`
   protocols. Never import Qdrant or Neo4j clients outside their adapters.
7. **Graceful degradation.** If a backing store is down, `/health/ready` reports `degraded` and the
   affected sub-question records an error. The workflow must not crash.
8. **No hidden reasoning exposed.** Observability shows decisions, queries, evidence and timings only.
9. **Every response carries `X-Request-ID`** (`backend/app/middleware/request_context.py`).
10. **No autonomous action.** The only mutations are document management. Destructive actions (document
    delete) go through the approval gate (`services/approval_service.py`).

### Explicit non-goals

No writes to systems of record. No autonomous actions. No fine-tuning. Not a general BI tool.

---

## 5. Security and RBAC

Enforced by `require_role` in `backend/app/core/security.py`.

| Role | Can | Cannot |
|---|---|---|
| `viewer` | read dashboards, browse entities and documents, read sessions | start research, upload, run Cypher |
| `analyst` | viewer + start research, upload, read-only Cypher, manage own memory | delete docs, reindex, approve |
| `admin` | everything | – |

A viewer calling `POST /api/v1/research` must get `403`. Uploads: ≤ `MAX_UPLOAD_MB` (5) and an extension
allowlist (md / txt / pdf). Rate limit: Redis token bucket at `RATE_LIMIT_PER_MINUTE` (120).

---

## 6. Configuration

Everything configurable lives in `backend/app/core/config.py` (`Settings`, cached with `@lru_cache`).
**Restart the backend after you edit `.env`.**

| Key | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `fake` | one of 8 providers via `get_llm()` |
| `VECTOR_STORE` | `memory` | or `qdrant` |
| `GRAPH_STORE` | `memory` | or `neo4j` |
| `MAX_SUBQUESTIONS` | 4 | setting it to 1 under-answers the canonical question |
| `MAX_CORRECTIVE_ROUNDS` | 1 | |
| `MAX_UPLOAD_MB` | 5 | |
| `RATE_LIMIT_PER_MINUTE` | 120 | |

---

## 7. Commands

Windows: the venv interpreter is `.venv/Scripts/python.exe`.

```bash
make setup                         # .venv + deps + .env
make demo                          # canonical question, prints every stage (~7 s offline)
make demo QUESTION="..."           # any question
make backend                       # FastAPI on :8001
make ingest                        # (re)index sample_data/documents
make seed-graph                    # rebuild graph (needed when running scripts directly)
make test                          # full offline suite
.venv/Scripts/python.exe -m tests.evaluation.evaluate   # metrics table
curl -s localhost:8001/health/ready | python -m json.tool
```

Offline `/health/ready` should report `memory (70 chunks)` and `memory (85 nodes, 260 edges)`.

---

## 8. Testing and evaluation

Every functional requirement (F1–F17 in `01-prd.md`) maps to a file and a test. When you add a feature,
add the row and the test together.

Key tests: `test_canonical_question_end_to_end`, `test_simple_question_single_subquestion`,
`test_research_lifecycle`, `test_auth_required_and_rbac`, `test_graph_traversals`,
`test_corrective_retrieval_triggers_for_unanswerable_part`, `test_multi_hop_citations_and_grounding`,
`test_upload_validation_and_ingest`, `test_graph_endpoints`,
`test_graph_shape_matches_frontend_assumptions`, `tests/unit/test_sql_validator.py` (8 tests).

Evaluation (`tests/evaluation/evaluate.py` over `datasets/eval_cases.json`). CI thresholds are deliberately
below the observed scores so CI fails on regressions and not on noise. Do not raise them to match the
observed scores.

| Metric | CI threshold | Observed |
|---|---|---|
| retrieval_relevance | ≥ 0.80 | 1.00 |
| sql_correctness | = 1.00 | 1.00 |
| graph_correctness | = 1.00 | 1.00 |
| multi_hop | ≥ 0.66 | 1.00 |
| citation_support | = 1.00 | 1.00 |
| answer_grounding | ≥ 0.50 | 1.00 |

---

## 9. Seed data (`sample_data/`)

6 teams · 20 employees · 8 services (Payments API, Identity Service, Data Pipeline, Analytics Dashboard,
Notification Service, Billing Engine, Customer Portal, Search Service) · 10 customers (enterprise /
mid-market / SMB) · 12 incidents over three quarters · 8 ADRs · 6 projects · 15 tickets ·
`organizational_memory.json` (incl. the fiscal calendar, which defines "last quarter") · 15 documents
(4 postmortems, 3 ADRs, 3 policies, 2 meeting notes, 1 runbook, 1 quarterly reliability summary,
1 hostile vendor note).

The data is built so the canonical question **needs** all three retrieval paths. If you change seed
data, re-check the canonical demo output and the evaluation metrics.

---

## 10. Working conventions for Claude

- Before you change a node, router rule or retriever, run `make demo` and the relevant test. Run them
  again afterwards and compare the stage output.
- Keep the API contract (`docs/API_CONTRACT.md`) and `docs/FRONTEND_ASSUMPTIONS.md` in sync with any
  response-shape change. The frontend depends on them.
- New data sources come in as `DocumentSource` adapters in `integrations/`. The retrieval architecture
  and the agents stay the same.
- Prefer deterministic rules plus validation over prompt tweaks when you fix routing or safety bugs.
- Never let a test or the demo require network access, Docker or a real API key.

### Common pitfalls

- Customers are seeded but documents are missing: run `make ingest`, or delete `data/enterprise.db`.
- Empty graph results: the graph is built at startup, so run `make seed-graph` when you call scripts directly.
- Circular import: `app.core.*` must never import `agents.*`.
- Two servers on :8001 (a container and a local uvicorn) give inconsistent results: check `docker ps`.
- A stale `.env`: `Settings` is cached, so restart the backend.

## 11. Production path (do not build unless asked)

Move graph execution to a worker (Celery / Cloud Tasks / SQS) and use `langgraph-checkpoint-postgres`.
Add per-tenant isolation with SQL RLS (`database/rls_policies.sql`), tenant-scoped graph labels and
Qdrant payload filters. Use Supabase for Auth, Storage and Postgres.