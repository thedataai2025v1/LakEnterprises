# Phase 1 — Project System Design Evolution

## Objective

Build a minimal runtime skeleton that validates the full call chain: CLI → config → LLM factory → pipeline orchestration → response.

## Decisions

### 1. Configuration: dataclass + env override

**Choice**: `Settings` as a frozen dataclass with env-var fallbacks in `__post_init__`.

**Alternatives considered**:
- **pydantic-settings**: heavier dependency, more boilerplate for v1 project.
- **Plain dict / os.environ reads scattered**: no validation, harder to test.

**Why**: A frozen dataclass is lightweight, self-documenting, and `inspect`-friendly. `dataclass.field()` with a default factory that reads the env gives the same ergonomics as pydantic without the dependency.

**Trade-off**: No automatic coercion or nested models. Acceptable for v1; Phase 2 can upgrade to pydantic if the Settings grows.

### 2. Singleton get_settings()

**Choice**: Module-level `_settings: Settings | None = None` and `get_settings()` that creates it once.

**Alternatives considered**:
- `functools.lru_cache` on `get_settings()`.
- Thread-safe double-checked locking.

**Why**: Simplest correct pattern for a single-threaded CLI tool. The `_settings` variable is set once and read without concurrency concerns.

**Trade-off**: Not thread-safe. Acceptable; the research pipeline runs single-thread.

### 3. Response as a plain dataclass (not AgentFinish)

**Choice**: `Response` is a dataclass with `answer`, `citations`, `metadata`, `error` — **not** a `langchain_core.agents.AgentFinish` subclass.

**Why**: LangChain's `AgentFinish` encodes internal agent-runtime details (`return_values`, `log`) that leak into the API contract. A dedicated `Response` keeps the public API stable and independent of LangChain's internal schema.

**Trade-off**: Extra mapping at pipeline boundaries. Small cost for a clean API.

### 4. Pipeline as a directed graph (LangGraph StateGraph)

**Choice**: `create_research_pipeline()` returns a `StateGraph` (from LangGraph) with `analyze_node`, `search_node`, `answer_node`.

**Alternatives considered**:
- **`langchain.chains.SequentialChain`**: linear only, harder to test nodes in isolation.
- **Plain functions called in order**: no visualisation, harder to extend.

**Why**: LangGraph gives a declarative node structure, `get_graph()` for debugging, and a natural path to Phase 4 (conditional edges, tool loops).

**Trade-off**: LangGraph is still evolving; the StateGraph API may change. We pin the dependency version in `requirements.txt`.

### 5. get_llm() requires explicit (provider, model)

**Choice**: `get_llm(provider: str, model: str, temperature=0.0, **kwargs)` — not `get_llm(settings: Settings)`.

**Why**: The function needs exactly the two values. Passing a whole `Settings` object couples the API to the config format and makes testing harder (you must construct a Settings just to get an LLM). Callers that want to use `get_settings()` do so explicitly at the call site.

**Trade-off**: Call sites are one line longer. Acceptable for clarity.

### 6. Embedding model is a factory, not a class

**Choice**: `get_embedding_model(provider, model, **kwargs)` returns a LangChain `Embeddings` instance.

**Why**: Same reasoning as `get_llm()`. Embeddings are stateless objects; a factory function is the right abstraction.

### 7. Test failures were test bugs, not source bugs

During Phase 1, 16 tests in `tests/test_pipeline.py` failed. Every failure was caused by the tests assuming a different API than the source code actually exposes:

| Failure | Cause | Fix |
|---|---|---|
| `Response(rv, log="")` | Test assumed old AgentFinish-like constructor | Use keyword args `Response(answer=..., citations=...)` |
| `r.return_values` | AgentFinish attribute on a plain dataclass | Remove assertion |
`isinstance(r, AgentFinish)` | Tests assumed Response subclassed AgentFinish | `isinstance(r, pipeline.Response)` |
| `from ... import _settings_cache` | Test assumed module-level cache variable was public | Remove import; don't clear cache in test |
| `s.PROVIDER_CONFIGS` | Name doesn't exist | Use `SUPPORTED_PROVIDERS` from `llm.py` |
| `get_llm(get_settings())` | Test passed Settings instead of (provider, model) | `get_llm(provider=s.llm_provider, model=s.llm_model)` |
| `get_embedding_model("openai", ...)` | Missing keyword names | Use keyword args |

**Lesson**: Write tests from the actual public API, not from a mental model of what the API "should be."

## What was dropped from the original plan

| Item | Reason |
|---|---|
| `_reset_settings()` test helper | Not part of the public API; tests should not reset singletons |
| `ProvderConfigs` in Settings | The config doesn't store per-provider configs — `llm.py` handles them internally |
| Thread-safe settings | Not needed for a CLI tool |
| pydantic models | Lighter to use dataclasses + env reads directly |

## Future-proofing

- The `StateGraph` from Phase 1 is the foundation for Phase 4's conditional edges and tool-calling agents.
- `Response.metadata` has a slot for `llm_provider` tracking — will be filled when Phase 2 adds model introspection.
- `retriever.create_retriever()` returns a stub that will be replaced with a real vector-store retriever in Phase 2, without changing the pipeline API.