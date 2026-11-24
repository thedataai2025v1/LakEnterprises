# LakEnterprises — Task tracker

> Concise checklist for GitHub-visible progress.
> Full plan: `docs/02-hld.md` · Phase exit criteria: `PLAN_PHASE.md` · Spec: `EURON.md`

**Branch convention:** `feature/<repo-name>` (one feature branch per sub-task; open the PR against `development`)
**Status:** `Pending ❌` · `Completed ✅`

Sub-tasks in the same phase that do not share files can be open at the same time. Do not stack a branch on another feature branch. Merge the listed predecessor first when a row names one.

`PLAN_PHASE.md` is still the exit-criteria spec. This file is the execution order, arranged so a phase waits only on the contract it uses.

---

## Phase 1 — Runtime skeleton

> Depends on: nothing. Unblocks: every later phase.
> Merge order: P1-1 first. P1-2 and P1-4 in parallel after it. P1-3 after P1-2.

| Task | Branch | Status |
|------|--------|--------|
| P1-1 · Project scaffold, config and structured logging | `feature/project-scaffold-config` | Completed ✅ |
| P1-2 · Health routes and request-id middleware | `feature/backend-health-request-id` | Completed ✅ |
| P1-3 · Offline pytest harness with fake LLM | `feature/test-harness-fake-llm` | Completed ✅ |
| P1-4 · Makefile, `.env.example` and `.gitignore` | `feature/makefile-env-example` | Completed ✅ |

---

## Phase 2 — Persistence and schemas

> Depends on: P1-1. Unblocks: Phases 3, 4, 5, 6, and 8.
> Merge order: P2-1 first. P2-2 and P2-3 in parallel after it. P2-4 after P2-3.

| Task | Branch | Status |
|------|--------|--------|
| P2-1 · SQLAlchemy entities and enums | `feature/sqlalchemy-entities` | Completed ✅ |
| P2-2 · Database schema, migrations and seed data | `feature/db-schema-migrations` | Completed ✅ |
| P2-3 · Repository layer | `feature/repository-layer` | Completed ✅ |
| P2-4 · Bootstrap data loader and demo fixtures | `feature/demo-data-bootstrap` | Completed ✅ |

---

## Phase 3 — Identity and access control

> Depends on: P1-2 and P2-1. Unblocks: protected routes in Phase 4 and Phase 12.
> Merge order: P3-1 first. P3-2 and P3-3 in parallel after it. P3-4 last.

| Task | Branch | Status |
|------|--------|--------|
| P3-1 · JWT service and RBAC decorator | `feature/jwt-rbac` | Completed ✅ |
| P3-2 · Auth routes and demo tokens | `feature/auth-demo-routes` | Completed ✅ |
| P3-3 · Rate limiting (Redis sliding window) | `feature/rate-limit-redis` | Completed ✅ |
| P3-4 · Audit middleware and middleware wiring | `feature/audit-middleware-wiring` | Completed ✅ |

---

## Phase 4 — Document processing pipeline

> Depends on: P2-3 and P3-1. Unblocks: Phases 5, 6. Does not block Phases 7 or 8.
> Merge order: P4-1 first. P4-2 and P4-3 in parallel after it. P4-4 after both.

| Task | Branch | Status |
|------|--------|--------|
| P4-1 · Document ingestion and chunking | `feature/doc-ingestion-chunking` | Completed ✅ |
| P4-2 · Vector store and embedding service | `feature/doc-vector-embeddings` | Completed ✅ |
| P4-3 · Hybrid retriever (vector + keyword) | `feature/doc-hybrid-retriever` | Completed ✅ |
| P4-4 · Document API and ingestion CLI | `feature/doc-ingest-api-cli` | Completed ✅ |

---

## Phase 5 — Enterprise process API

> Depends on: P2-3 and P3-1. Parallel with: Phases 4, 7, 8.
> Merge order: P5-1 first. P5-2 and P5-3 in parallel after it. P5-4 after both.

| Task | Branch | Status |
|------|--------|--------|
| P5-1 · Process template CRUD | `feature/process-template-crud` | Completed ✅ |
| P5-2 · Process instance API and state machine | `feature/process-instance-state` | Completed ✅ |
| P5-3 · Task and approval API | `feature/task-approval-api` | Completed ✅ |
| P5-4 · Process run CLI and demo script | `feature/process-run-demo` | Completed ✅ |

---

## Phase 6 — Agent tools and integrations

> Depends on: P4-1 and P5-1. Parallel with: Phases 7, 8.
> Merge order: P6-1 and P6-4 in parallel. P6-2 and P6-3 in parallel after both.

| Task | Branch | Status |
|------|--------|--------|
| P6-1 · Tool registry and policy engine | `feature/tool-registry-policy` | Completed ✅ |
| P6-2 · Read-only enterprise tools (search, lookup) | `feature/tools-read-only` | Completed ✅ |
| P6-3 · Approval-gated write tools (submit, approve) | `feature/tools-approval-gated` | Completed ✅ |
| P6-4 · Mock enterprise integrations (ERP, CRM, email) | `feature/integrations-mock-enterprise` | Completed ✅ |

---

## Phase 7 — Guardrails and security

> Depends on: P2-1. Parallel with: Phases 4, 5, 6, 8.
> Merge order: all four branches can be open together. They live in separate modules.

| Task | Branch | Status |
|------|--------|--------|
| P7-1 · PII/secret scrubber middleware | `feature/guardrail-secret-scrub` | Completed ✅ |
| P7-2 · Prompt injection guard | `feature/guardrail-injection` | Completed ✅ |
| P7-3 · Output schema validation | `feature/guardrail-output-validation` | Completed ✅ |
| P7-4 · Escalation and severity rules engine | `feature/policy-escalation-rules` | Completed ✅ |

---

## Phase 8 — Enterprise memory

> Depends on: P2-3 and P7-1. Parallel with: Phase 12. Does not wait on Phase 9.
> Merge order: P8-1 and P8-2 in parallel. P8-3 after both.

| Task | Branch | Status |
|------|--------|--------|
| P8-1 · Short-term session store (Redis) | `feature/memory-short-term-redis` | Completed ✅ |
| P8-2 · Long-term process memory store | `feature/memory-long-term` | Completed ✅ |
| P8-3 · Memory recall and write-back service | `feature/memory-recall-service` | Completed ✅ |

---

## Phase 9 — Specialist agents

> Depends on: Phases 4, 5, 6, 7, and 8. Parallel with: nothing required inside the phase after P9-1.
> Merge order: P9-1 first. P9-2 through P9-7 in parallel after it. Each agent branch carries its own test.

| Task | Branch | Status |
|------|--------|--------|
| P9-1 · Workflow schemas and fake LLM harness | `feature/workflow-schemas-fake-llm` | Completed ✅ |
| P9-2 · Supervisor / orchestrator agent | `feature/agent-supervisor` | Completed ✅ |
| P9-3 · Document analysis agent | `feature/agent-document-analyst` | Completed ✅ |
| P9-4 · Compliance check agent | `feature/agent-compliance` | Completed ✅ |
| P9-5 · Knowledge retrieval agent | `feature/agent-knowledge-retrieval` | Completed ✅ |
| P9-6 · Resolution / response drafting agent | `feature/agent-response-draft` | Completed ✅ |
| P9-7 · Escalation and handoff agent | `feature/agent-escalation-handoff` | Completed ✅ |
| P9-8 · Eval case dataset and tests | `feature/agent-eval-dataset` | Completed ✅ |

---

## Phase 10 — Workflow graph and tracing

> Depends on: Phase 9. Unblocks: Phase 11.
> Merge order: P10-1 first. P10-2, P10-3, P10-4, and P10-6 in parallel. P10-5 after all (wires the graph).

| Task | Branch | Status |
|------|--------|--------|
| P10-1 · Process state and checkpointer | `feature/graph-state-checkpointer` | Completed ✅ |
| P10-2 · Orchestrator graph nodes | `feature/graph-nodes-orchestrator` | Completed ✅ |
| P10-3 · Document investigation graph nodes | `feature/graph-nodes-investigate` | Completed ✅ |
| P10-4 · Resolution and risk graph nodes | `feature/graph-nodes-resolution` | Completed ✅ |
| P10-5 · Graph wiring and run endpoint | `feature/graph-wiring-run-api` | Completed ✅ |
| P10-6 · Workflow tracer and events stream | `feature/workflow-tracer-events` | Completed ✅ |

---

## Phase 11 — Approval and escalation runtime

> Depends on: P6-3 and Phase 10. Unblocks: the process action UI and `make demo`.
> Merge order: P11-1 and P11-3 in parallel. P11-2 after P11-1. P11-4 after P11-1 and P11-3. P11-5 last.

| Task | Branch | Status |
|------|--------|--------|
| P11-1 · Human approval interrupt node | `feature/workflow-human-approval` | Completed ✅ |
| P11-2 · Approval decide and resume API | `feature/api-approvals-resume` | Completed ✅ |
| P11-3 · Escalation routing and SLA timer | `feature/workflow-escalation-routing` | Completed ✅ |
| P11-4 · Execute resolution via shared tool path | `feature/workflow-execute-resolution` | Completed ✅ |
| P11-5 · Demo script for end-to-end process | `feature/demo-e2e-process` | Completed ✅ |

---

## Phase 12 — Console UI shell

> Depends on: P5-1 and P3-2. Parallel with: Phases 4 through 11 (except Phase 13).
> Merge order: P12-1 and P12-2 in parallel. P12-3 after both. P12-4 after P12-3.

| Task | Branch | Status |
|------|--------|--------|
| P12-1 · Next.js app shell and navigation | `feature/frontend-app-shell` | Completed ✅ |
| P12-2 · Typed API client (auto-generated) | `feature/frontend-api-client` | Completed ✅ |
| P12-3 · Login, RBAC layout, and session | `feature/frontend-auth-layout` | Completed ✅ |
| P12-4 · Dashboard and list pages | `feature/frontend-dashboard-pages` | Completed ✅ |

---

## Phase 13 — Process workflow screen

> Depends on: Phase 11 and Phase 12. Only UI phase that waits on the graph.
> Merge order: P13-1 first. P13-2 and P13-3 in parallel after it. P13-4 after both.

| Task | Branch | Status |
|------|--------|--------|
| P13-1 · Process detail and timeline layout | `feature/frontend-process-layout` | Pending ❌ |
| P13-2 · Workflow steps panel with polling | `feature/frontend-workflow-panel` | Pending ❌ |
| P13-3 · Approve, reject, escalate actions UI | `feature/frontend-process-actions` | Pending ❌ |
| P13-4 · Frontend integration tests | `feature/frontend-integration-tests` | Pending ❌ |

---

## Phase 14 — Production hardening

> Depends on: Phase 11 and Phase 13. Final phase before `main` release.
> Merge order: P14-1 and P14-2 in parallel. P14-3 and P14-4 in parallel after both. P14-5 last.

| Task | Branch | Status |
|------|--------|--------|
| P14-1 · Rate limiting, CORS, and security headers | `feature/prod-security-headers` | Pending ❌ |
| P14-2 · Docker Compose for local prod-like stack | `feature/docker-compose-stack` | Pending ❌ |
| P14-3 · API documentation (OpenAPI / Redoc) | `feature/api-docs-openapi` | Pending ❌ |
| P14-4 · End-to-end smoke tests | `feature/e2e-smoke-tests` | Pending ❌ |
| P14-5 · Deployment guide and runbook | `feature/deployment-guide-runbook` | Pending ❌ |