<!-- Written by Euron Code after each task. It is rewritten automatically: put your own rules in
     another file in .euron/rules/. -->

# Learned in this project

- Tests: `if (Test-Path tests) { python -m pytest tests/ -v 2>&1 } else { Write-Host "No tests directory found" }` works here (passed 1x, last 2026-11-22). Use it to verify changes.

## Security (from .euron/security/assessment.md)
- This code base has had: html inserted without escaping (xss) (SEC050). Render text, or sanitise the HTML (DOMPurify / bleach) before inserting it. Do not add more; fix the existing ones when you touch those files.
