# 01 – Product Requirements Document

## What are we building?

A research platform where an analyst asks one enterprise question in natural language and receives a
**cited, verified answer** assembled from documents, database records and a knowledge graph – with the
whole retrieval process open to inspection.

## Why?

A PRD forces the fuzzy ambition ("make our knowledge searchable") into testable requirements. Every
requirement below maps to code you can point at and a test that proves it.

## Which concept does it teach?

Writing requirements for a *non-deterministic* system: you cannot specify the exact wording of an
answer, so you specify the **evidence, citations, strategies, latency and safety** around it instead.

---

## 1. Users and roles

| Role | Can | Cannot |
|---|---|---|
| `viewer` | read dashboards, browse customers / incidents / decisions / documents, read research sessions | start research, upload, run Cypher |
| `analyst` | everything a viewer can, plus start research, upload documents, run read-only Cypher, manage own memory | delete documents, reindex, approve |
| `admin` | everything, plus reindex, approve/reject approval requests, delete documents | – |

Enforced by `require_role` in `backend/app/core/security.py`; `tests/api/test_api.py::test_auth_required_and_rbac`
proves a viewer gets `403` on `POST /api/v1/research`.

## 2. Functional requirements

| # | Requirement | Where it lives | Proven by |
|---|---|---|---|
| F1 | Accept a natural-language question and return a session id immediately (202) | `backend/app/api/research.py` | `test_research_lifecycle` |
| F2 | Analyse intent, entities, time range, and whether relationships / aggregation are needed | `agents/nodes/analyze_query.py` | `test_canonical_question_end_to_end` |
| F3 | Classify complexity `simple / moderate / complex` | `agents/nodes/assess_complexity.py`, `agents/rules.py` | `test_simple_question_single_subquestion` |
| F4 | Decompose a complex question into ≤ `MAX_SUBQUESTIONS` (default 4) sub-questions | `agents/nodes/decompose.py` | `test_canonical_question_end_to_end` |
| F5 | Route each sub-question to vector, SQL, graph or hybrid retrieval | `agents/nodes/route_retrieval.py` | `test_graph_shape_matches_frontend_assumptions` |
| F6 | Hybrid document retrieval: semantic + BM25 + RRF + rerank | `rag/retriever.py` | `tests/rag/test_retrieval_graph.py` |
| F7 | SQL retrieval restricted to a read-only allowlist | `rag/sql_retrieval.py` | `tests/unit/test_sql_validator.py` (8 tests) |
| F8 | Graph retrieval via typed traversals that also expose their Cypher | `rag/graph_store.py` | `test_graph_traversals` |
| F9 | Detect missing evidence and run at most `MAX_CORRECTIVE_ROUNDS` corrective retrievals | `agents/nodes/check_missing_evidence.py`, `corrective_retrieval.py` | `test_corrective_retrieval_triggers_for_unanswerable_part` |
| F10 | Verify each claim against collected evidence before answering | `agents/nodes/verify_evidence.py` | `test_canonical_question_end_to_end` |
| F11 | Answer carries `[n]` citation markers resolvable to evidence | `agents/nodes/synthesize_answer.py` | `test_multi_hop_citations_and_grounding` |
| F12 | Verify every citation resolves; report invalid ones | `agents/nodes/verify_citations.py` | `test_research_lifecycle` |
| F13 | Ingest markdown / text / PDF documents, chunk, extract entities and relationships, index into vector + DB + graph | `rag/ingest.py` | `test_upload_validation_and_ingest` |
| F14 | Browse the knowledge graph and expand nodes | `backend/app/api/graph.py` | `test_graph_endpoints` |
| F15 | Four separated memory scopes surfaced per session | `memory/memory_service.py` | `test_research_lifecycle` |
| F16 | Expose every node transition, tool call, query and timing | `backend/app/core/observability.py` | `GET /api/v1/research/{id}/events` |
| F17 | Approval gate on destructive admin actions (document delete) | `backend/app/api/documents.py`, `services/approval_service.py` | `test_upload_validation_and_ingest` |

## 3. Non-functional requirements

| # | Requirement | Target | Notes |
|---|---|---|---|
| N1 | Runs with **no API key and no external service** | `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`, SQLite, fakeredis | the entire test suite and `make demo` |
| N2 | Provider-agnostic AI | 8 providers via `get_llm()` / `get_embedding_model()` | `backend/app/core/llm.py` |
| N3 | Replaceable stores | `VectorStoreService` and `GraphStoreService` protocols | `rag/vector_store.py`, `rag/graph_store.py` |
| N4 | Canonical question completes offline | ~7 s (fake provider, memory stores) | measured by `make demo` |
| N5 | Every response carries `X-Request-ID` | middleware | `backend/app/middleware/request_context.py` |
| N6 | Rate limiting | `RATE_LIMIT_PER_MINUTE` (default 120) | Redis token bucket |
| N7 | Uploads validated | ≤ `MAX_UPLOAD_MB` (5), extension allowlist | `backend/app/api/documents.py` |
| N8 | Untrusted content never becomes instructions | wrapped + scanned + flagged | `backend/app/core/guardrails.py` |
| N9 | No hidden reasoning exposed | only decisions, queries, evidence, timings | `16-observability.md` |

## 4. Explicit non-goals

- No write access to the enterprise systems of record. Every SQL statement and every Cypher query is read-only.
- No autonomous action. The platform answers questions; the only mutations are document management, and destructive ones need approval.
- No fine-tuning or model training.
- Not a general BI tool: SQL is limited to an allowlisted schema, not arbitrary analytics.

## 5. Success metrics (measured, not asserted)

`tests/evaluation/evaluate.py` scores the system on a fixed dataset (`tests/evaluation/datasets/eval_cases.json`):

| Metric | Threshold in CI | Observed offline |
|---|---|---|
| retrieval relevance | ≥ 0.80 | 1.00 |
| SQL correctness | = 1.00 | 1.00 |
| graph correctness | = 1.00 | 1.00 |
| multi-hop coverage | ≥ 0.66 | 1.00 |
| citation support | = 1.00 | 1.00 |
| answer grounding | ≥ 0.50 | 1.00 |

## Files to open

- `docs/API_CONTRACT.md` – the HTTP contract the frontend was built against
- `docs/FRONTEND_ASSUMPTIONS.md` – the extra guarantees the UI depends on
- `backend/app/core/config.py` – every requirement that is configurable
- `tests/evaluation/datasets/eval_cases.json`

## Command to run

```bash
make test                                   # every requirement above, offline
.venv/Scripts/python.exe -m tests.evaluation.evaluate     # the metrics table
```

## What students should observe

```text
metric                   score
retrieval_relevance       1.00
sql_correctness           1.00
graph_correctness         1.00
multi_hop                 1.00
citation_support          1.00
answer_grounding          1.00
```

The thresholds in `tests/evaluation/test_evaluation.py` are deliberately lower than the observed scores:
an evaluation suite should fail on regression, not on noise.

## Modification students can try

Add a requirement: "an answer must carry at least three citations". Encode it as a case in
`tests/evaluation/datasets/eval_cases.json`, add the metric to `evaluate.py`, and watch it fail for the
simple data-retention question (which only has three) before you tune it.

## Common errors

- Editing `.env` but not restarting the backend – `Settings` is cached with `@lru_cache`.
- Setting `MAX_SUBQUESTIONS=1` and then wondering why the canonical question is under-answered; the corrective loop cannot fix a decomposition that was never allowed to happen.

## Production extension

Add per-tenant requirements: row-level filters in SQL, graph labels scoped by tenant, and Qdrant payload
filters. `database/rls_policies.sql` shows the Supabase side of that.
