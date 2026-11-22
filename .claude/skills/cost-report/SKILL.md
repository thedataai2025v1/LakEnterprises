---
name: cost-report
description: Show Claude Code usage cost, cache-read share, and per-agent breakdown
model: haiku
---

Generate a cost and usage report.

Run `python scripts/claude_usage/report.py` if the script exists. Otherwise, use `/cost` to get current session data.

Report the following:
1. **Total cost** for the current session.
2. **Cache-read share**: percentage of input tokens that were cache reads (last 7 days if data available).
3. **Per-agent cost**: breakdown by agent type if usage data includes agent identity. If not available, state: "Per-agent breakdown unavailable on this version."
4. **Model usage**: tokens by model tier (Opus, Sonnet, Haiku).

A drop in cache-read share after a rollout means something is breaking the cached prefix.

$ARGUMENTS
