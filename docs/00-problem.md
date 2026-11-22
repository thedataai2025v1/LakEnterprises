# 00 – The Business Problem

## What are we building?

An **Enterprise Knowledge & Decision Intelligence Platform** for a fictional technology company,
**NovaEnterprise**. The platform answers questions that span documents, records *and* relationships:

```text
Vector RAG  +  Graph RAG  +  SQL  +  Agents  +  Memory
```

The question every stage of this project is built around – the **canonical question**:

> Which customers were impacted by the Payments API last quarter, what incidents occurred,
> which teams own those services, and what decisions were taken to prevent recurrence?

No single retrieval call answers that. It needs four different lookups, in four different stores,
merged into one cited answer.

## Why?

Enterprise information is scattered: PDFs and policies, meeting notes, ticket tables, incident records,
architectural decisions, employees, teams, customers. A plain "chat with your documents" bot fails here
in three specific ways:

| The question needs… | Plain vector RAG | This platform |
|---|---|---|
| **Records and counts** ("which incidents in Q2?") | guesses from prose | `SQLAgent` runs a validated read-only `SELECT` |
| **Relationships** ("which customers did that incident impact?") | cannot traverse | `GraphAgent` runs a Cypher traversal in Neo4j |
| **Narrative** ("what did we decide and why?") | good | hybrid vector + BM25 search over postmortems and ADRs |
| **Several of the above at once** | one query, one shot | decomposition into sub-questions, one strategy each |
| **Trustworthiness** | fluent but unverified | evidence verification + citation verification before the answer ships |

## Which concept does it teach?

That **retrieval strategy is a routing decision, not a library choice**. Students learn to look at a
question, identify which part is a document question, which part is a records question and which part is
a relationship question, and to build a system that decides this at run time instead of hard-coding one
retriever.

## The demo enterprise

NovaEnterprise is seeded from `sample_data/`:

| File | Contents |
|---|---|
| `teams.json` | 6 teams (Payments Platform, Identity, Data Platform, Customer Success, SRE, Analytics) |
| `employees.json` | 20 employees with titles and team membership |
| `services.json` | 8 services (Payments API, Identity Service, Data Pipeline, Analytics Dashboard, Notification Service, Billing Engine, Customer Portal, Search Service) |
| `customers.json` | 10 customers across enterprise / mid-market / SMB tiers |
| `incidents.json` | 12 incidents across three quarters, with root causes and impacted customers |
| `decisions.json` | 8 architectural decisions (ADRs) that address those incidents |
| `projects.json`, `tickets.json` | 6 projects, 15 tickets |
| `organizational_memory.json` | curated shared facts (e.g. the fiscal calendar) |
| `documents/*.md` | 15 documents: 4 postmortems, 3 ADRs, 3 policies, 2 sets of meeting notes, a runbook, a quarterly reliability summary, and one hostile vendor note |

The data is designed so the canonical question **must** use all three retrieval paths:

| Part of the question | Answered from | Why not the others |
|---|---|---|
| which customers were impacted | **graph** `(Service)<-[:AFFECTED]-(Incident)-[:IMPACTED]->(Customer)` | the link lives in relationships, not prose |
| what incidents occurred | **SQL** `incidents JOIN services` filtered by date | needs exact records in a date range |
| which teams own those services | **graph** `(Service)-[:OWNED_BY]->(Team)` | one hop, no document says it plainly |
| what decisions prevent recurrence | **hybrid** postmortems + ADR documents (+ graph) | the rationale is narrative text |

`sample_data/documents/vendor-note-processor-update.md` contains a deliberate prompt-injection attempt.
It must be **indexed as data and flagged**, never obeyed – see `05-rag.md` and `06-tools.md`.

## Files to open

- `README.md` – project overview and quick start
- `sample_data/incidents.json`, `sample_data/decisions.json`, `sample_data/services.json`
- `sample_data/documents/postmortem-inc-2031-payments-api-outage.md` – the SEV1 the question is about
- `sample_data/documents/vendor-note-processor-update.md` – the hostile document
- `agents/rules.py` – the deterministic analysis, decomposition and routing rules

## Command to run

```bash
cd project-02-enterprise-intelligence
make setup            # .venv + deps + .env
make demo             # asks the canonical question and prints every stage
```

## What students should observe

`make demo` prints, in order: the analysis (complexity `complex`, entity `Payments API`, time range
`last quarter`), four sub-questions with one strategy each, the SQL that ran, the three Cypher
traversals, nine pieces of evidence, a verification ratio, and a cited answer:

```text
=== QUERY DECOMPOSITION ===================================================
  sq1 [ graph] Which customers were impacted by the Payments API last quarter?  (done)
  sq2 [   sql] What incidents occurred for Payments API last quarter?  (done)
  sq3 [ graph] Which teams own those services for Payments API last quarter?  (done)
  sq4 [hybrid] What decisions were taken to prevent recurrence for Payments API last quarter?  (done)

=== STRATEGIES USED =======================================================
   graph, sql, vector (corrective rounds: 0)
```

That single command already demonstrates the entire problem statement.

## Modification students can try

Ask a question that only needs one store, for example `make demo QUESTION="What is our data retention
policy?"`. Observe that complexity drops to `simple`, there is exactly one sub-question, no SQL and no
Cypher run, and `strategies_used` contains only `vector`. The router adapts; the code does not change.

## Common errors

- `10 customers` already seeded but documents missing → run `make ingest` (or delete `data/enterprise.db` and re-run `make demo`).
- Empty graph results → the graph is built at startup; run `make seed-graph` if you ran a script directly.

## Production extension

Point the pipeline at real sources through `integrations/protocols.py` (`DocumentSource`): Confluence,
SharePoint, Google Drive, a ticketing API. The retrieval architecture and the agents stay identical;
only the ingestion adapters change.
