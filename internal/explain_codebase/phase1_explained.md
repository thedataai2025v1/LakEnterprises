# Phase 1 — Runtime Skeleton Explained

## Purpose

Phase 1 delivers the minimal runnable project: a config module, an LLM factory, a retriever stub, a pipeline orchestration class, and a CLI entry point. The design deliberately postpones persistence, embedding retrieval, and a multi-turn loop — those come in Phases 2–4.

## Architecture overview

```
CLI (__main__.py)
    │
    ▼
config.py ─► pipeline.py ◄─ llm.py
                    │
                    ▼
              retriever.py (stub)
```

- **`config.py`**: `Settings` dataclass with env-var overrides, singleton `get_settings()`.
- **`llm.py`**: Factory functions `get_llm()` and `get_embedding_model()` that return LangChain objects.
- **`retriever.py`**: Placeholder `create_retriever()` returning a self-documenting stub; no real vector DB connection yet.
- **`pipeline.py`**: `create_research_pipeline()` builds a directed graph (via LangGraph). Each node is a function that stores results in a shared state dict. The top-level `run_pipeline()` drives execution.
- **`__main__.py`**: CLI that reads a query, calls `run_pipeline()`, and prints the `Response`.

## Key types

| Type | Where | Role |
|---|---|---|
| `Settings` | `config.py` | Holds `llm_provider`, `llm_model`, `embedding_provider`, `embedding_model`, `db_url`, etc. |
| `Response` | `pipeline.py` | Dataclass with `answer`, `citations`, `metadata`, `error` — the output contract. |
| `GraphState` | `pipeline.py` | TypedDict representing the runtime state passed between nodes. |

## Node flow

```
analyze_node(graph_state)  ──► ResearchPlan
    │
    ▼
search_node(research_plan) ──► list[SearchResult]  
    │
    ▼
answer_node(graph_state)   ──► Response
```

Each node gets what it needs from the shared graph state, reads config via `get_settings()`, and uses `get_llm()` for any LLM call. This keeps the graph definition declarative and the nodes testable in isolation.

## Provider support

`SUPPORTED_PROVIDERS` in `llm.py` lists known vendors (openai, anthropic, google, azure, cohere, groq, together, ollama). `get_llm()` calls the right LangChain ChatModel constructor. `get_embedding_model()` does the same for embeddings.

## What is intentionally missing (postponed to later phases)

- Real embedding store / vector DB (Phase 2)
- Multi-turn conversation loop (Phase 3)
- Tool-calling agents and dynamic DAG (Phase 4)
- Production-quality error recovery and observability (Phase 4+)

## Test strategy

Tests in `tests/test_pipeline.py` exercise:
- The `Response` dataclass construction and defaults.
- `Settings` construction and env-var forwarding.
- `SUPPORTED_PROVIDERS` keys.
- `get_settings()` singleton behaviour (returns the same instance each call).
- Pipeline creation: `create_research_pipeline()` returns a `StateGraph` with the expected nodes.
- Node isolation: each pipeline node runs standalone with minimal state.
- End-to-end: `run_pipeline()` produces a well-typed `Response` for the canned demo question.

Tests that require `OPENAI_API_KEY` are `@pytest.mark.skipif`-guarded and skipped when the env var is absent.