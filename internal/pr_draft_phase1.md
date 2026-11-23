# PR: Phase 1 — Runtime Skeleton

## Summary

Deliver the minimal runnable research pipeline: config, LLM factory, pipeline orchestration (LangGraph), retriever stub, and CLI entry point. All 34 tests pass (32 passed, 2 skipped for missing API key).

## Changes

### New files
- `src/lakenterprises/config.py` — `Settings` dataclass with env-var fallbacks, singleton `get_settings()`
- `src/lakenterprises/llm.py` — `get_llm()` and `get_embedding_model()` factories for 8 providers
- `src/lakenterprises/retriever.py` — stub `create_retriever()` (real backend in Phase 2)
- `src/lakenterprises/pipeline.py` — `Response` dataclass, `GraphState`, `create_research_pipeline()`, `run_pipeline()`
- `src/lakenterprises/__main__.py` — CLI (reads query → runs pipeline → prints response)
- `tests/test_pipeline.py` — 34 tests covering Response, Settings, pipeline nodes, e2e
- `internal/explain_codebase/phase1_explained.md` — codebase walkthrough
- `internal/design_evolution/Phase1_Project_System_Design_Evolution.md` — architecture decisions
- `requirements.txt` — pinned dependencies (langchain, langgraph, httpx, etc.)
- `.gitignore`, `pyproject.toml`

### Changed files
- `tests/test_pipeline.py` — fixed 16 test bugs (wrong constructor, wrong imports, wrong assertions)

## Verification

```bash
python -m pytest tests/test_pipeline.py -v
# 32 passed, 2 skipped (OPENAI_API_KEY needed)
python -c "from lakenterprises import pipeline; print('Import OK')"
python -c "from lakenterprises import config; cfg = config.get_settings(); print(f'{cfg.llm_provider=}, {cfg.llm_model=}')"
python -c "from lakenterprises.pipeline import run_pipeline; r = run_pipeline('test query'); print(r.answer[:50])"
```

## Breaking changes

None. This is the initial scaffolding.

## Next

Phase 2: real vector-store retriever, multi-query expansion, and source citation.