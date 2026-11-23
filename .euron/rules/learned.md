<!-- Written by Euron Code after each task. It is rewritten automatically: put your own rules in
     another file in .euron/rules/. -->

# Learned in this project

- Tests: `cd C:/Lak-Learn/Lak_AI/Agentic-AI-Projs/LakEnterprises; python -c " from lakenterprises import pipeline from unittest.m…` works here (passed 2x, last 2026-11-23). Use it to verify changes.
- Tests: `cd C:/Lak-Learn/Lak_AI/Agentic-AI-Projs/LakEnterprises; python -c " from unittest.mock import MagicMock from lakenterpr…` works here (passed 2x, last 2026-11-23). Use it to verify changes.
- Tests: `cd C:/Lak-Learn/Lak_AI/Agentic-AI-Projs/LakEnterprises; python -m pytest tests/test_pipeline.py -v --tb=short 2>&1` has failed 6x and never passed; check why before relying on it.
- Tests: `cd C:/Lak-Learn/Lak_AI/Agentic-AI-Projs/LakEnterprises; python -m pytest tests/test_pipeline.py -v --tb=short 2>&1 | Se…` has failed 3x and never passed; check why before relying on it.

## Security (from .euron/security/assessment.md)
- This code base has had: html inserted without escaping (xss) (SEC050). Render text, or sanitise the HTML (DOMPurify / bleach) before inserting it. Do not add more; fix the existing ones when you touch those files.
