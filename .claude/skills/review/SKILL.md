---
name: review
description: Review code changes for correctness and architecture compliance
context: fork
agent: code-reviewer
---

Review the following code changes:

$ARGUMENTS

Produce a ranked findings list. Check layer rules, circular imports, security, and test coverage.
