# Claude Code Usage Report

This directory contains the usage report script for Claude Code cost tracking.

## Setup

The `report.py` script (when created) uses Python stdlib only — no additional dependencies.

## Usage

```bash
python scripts/claude_usage/report.py
```

## Metrics

The report should show:

1. **Total cost** — session and cumulative
2. **Cache-read share** — percentage of input tokens served from cache (last 7 days)
3. **Per-agent cost** — breakdown by agent type (if usage data includes agent identity)
4. **Model usage** — tokens and cost by model tier (Opus, Sonnet, Haiku)

> **Note:** The actual `report.py` script has not been created yet. Create it when ready
> to implement cost tracking against Claude Code's usage data format.

## Cache health

A drop in cache-read share after a rollout means something is breaking the cached prefix.
Common causes:
- Editing CLAUDE.md, rules, or agent definitions mid-session
- Adding/removing MCP servers mid-session
- Using `/model` to switch models mid-session
