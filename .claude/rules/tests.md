---
paths:
  - "tests/**"
  - "tests/"
---

# Test conventions

- All tests must run offline with `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`.
- Use `python -m pytest <file>` for targeted runs, `python -m pytest` for full suite.
- Follow existing patterns in `tests/api/test_api.py` and `tests/unit/test_sql_validator.py`.
- Each test file tests one module or feature. Name: `test_<module>.py`.
- Use fixtures for shared setup. Avoid global state.
- Assert specific values, not just "no exception."
- Run `ruff check` and `mypy` before committing test changes.
- Never import from `agents.*` inside `app.core.*` test helpers — same circular import rule as production code.
