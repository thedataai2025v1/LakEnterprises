# Claude Code Setup — Suggestions & Configuration Report

> Generated: 2026-11-22
> This is the only file that proposes changes to protected files.

---

## 1. Protected files found

| Path | Lines | Location |
|---|---|---|
| `CLAUDE.md` | 405 | Root (protected — not edited) |

No `SKILLS.md` files found anywhere in the project.

---

## 2. Suggested changes to `CLAUDE.md`

The root `CLAUDE.md` is comprehensive (405 lines, exceeds the 150-line guideline) and covers the full architecture. It is **protected and was not modified**.

### Missing sections

- **Cost and delegation section** — The file has no cost governance or Claude Code delegation rules. Suggest adding a `§21. Cost & Delegation` section with the following content:

```markdown
## 21. Cost & Delegation

1. Finish one task before starting another.
2. Keep a session for one topic.
3. Do not edit CLAUDE.md, rules, or agents during a session — changes invalidate the prompt cache.
4. Do not add or remove MCP servers mid-session.
5. Batch questions instead of asking one at a time.
6. Use named skills: `/plan`, `/implement`, `/test`, `/review`, `/consult-opus`.
7. Use `log-triage` for long command output.
8. Commit only after code review and green tests.
9. Route to cheapest tier: Haiku for search/triage, Sonnet for code, Opus for architecture only.
```

### Conflicts with cost plan

- §20 "Development Workflow" step 9 says "regressions must be caught before commit" — this aligns with the cost plan. No conflict.
- No auto-commit rules found. No conflict.

### Content that belongs in `.claude/rules/`

- §5 "Layer Rules" and §8 "Import Direction" → already extracted to `.claude/rules/architecture.md`
- §14 "Key Test Files" conventions → already extracted to `.claude/rules/tests.md`

### Cache rule

Add to CLAUDE.md: "Do not edit CLAUDE.md, `.claude/rules/`, or `.claude/agents/` during a session. Changes invalidate the prompt cache."

---

## 3. Suggested changes to SKILLS.md

No `SKILLS.md` files found. No migration needed.

**Note:** Claude Code loads skills from `.claude/skills/<name>/SKILL.md`, not from `SKILLS.md` files. If `SKILLS.md` files are created in the future, their content should be migrated to the `.claude/skills/` structure with proper `name` and `description` frontmatter.

---

## 4. Per-run budgets for each agent type

These are guidelines, not hard limits. Exceeding a guideline is a signal to split the task.

| Agent | Max tool calls per run | Rationale |
|---|---|---|
| Explore | 10 | Search-only, should find quickly |
| log-triage | 8 | Read + grep, brief triage |
| opus-consultant | 5 | Read-only, one focused answer |
| planner | 30 | Read + write one plan file |
| architect | 30 | Read + write one ADR |
| implementer | 120 | Full edit cycle with tests |
| test-engineer | 80 | Write tests + run them |
| code-reviewer | 30 | Read diff + grep for issues |

---

## 5. Suggested changes to other markdown

### Agent descriptions

All agent `description` fields include "Delegate here" and a trigger — verified.

### Rules file lengths

| File | Lines | Status |
|---|---|---|
| `.claude/rules/tests.md` | 14 | ✅ Under 30 |
| `.claude/rules/architecture.md` | 16 | ✅ Under 30 |
| `.claude/rules/cost-and-delegation.md` | 16 | ✅ Under 30 |

### READMEs

- `README.md` — Empty. No old setup to update.
- `docs/03-claude_project_setup_prompt_txt.md` — Contains the prompt used to generate this setup. No conflict.

---

## 6. Prompt caching decisions

### TTL decision

- **Claude Code CLI not found on PATH.** Cannot determine version or platform (Vertex AI vs. first-party API).
- **Decision: `<DECIDE: probe result>`** — TTL key is NOT set in `settings.json`. The 5-minute default applies.
- **Rationale:** Without knowing the platform pricing, cannot confirm that the 1-hour write cost is justified. Leave as default until `claude --version` is available and a probe can be run.

### Cache stability measures applied

- Rules, agents, and skills are set up between sessions (not during).
- `cost-and-delegation.md` rule #3 and #10 enforce this.
- Agent prompts are short and stable.
- MCP servers are not configured mid-session (rule #4).

### Two-turn cache verification

- **Status: NOT YET RUN.** Claude Code CLI is not installed. The two-turn test must be performed in a fresh Claude Code session after installation.
- **Procedure:** Send one short message → note cache-write tokens → send a second message within 1 minute → verify cache-read tokens appear.

---

## 7. Items to verify on the pinned version

| Item | Status | Notes |
|---|---|---|
| `CLAUDE_MODEL_OPUS` env key | `<PIN: ...>` | Set to actual model ID after checking `claude` CLI |
| `CLAUDE_MODEL_SONNET` env key | `<PIN: ...>` | Set to actual model ID |
| `CLAUDE_MODEL_HAIKU` env key | `<PIN: ...>` | Set to actual model ID |
| `CLAUDE_CODE_PROMPT_CACHE_TTL` | Not set | Using 5-min default; probe needed |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Set to `sonnet` | Verify it's honoured |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | Set to `2` | **Unverified** |
| `omitClaudeMd: true` on log-triage | Set | **Unverified** |
| `Agent(opus-consultant)` tool syntax | Used in implementer, test-engineer, code-reviewer | **Unverified** — check Claude Code docs |
| Hook JSON format (`PreToolUse`) | Set in settings.json | **Unverified** — check Claude Code version |
| Unscoped rules loading | `cost-and-delegation.md` has no `paths:` | **Unverified** — must load every session |
| Agent identity in usage data | Unknown | Per-agent cost tracking may be unavailable |
| `model` field in agent frontmatter | Set on all agents | **Unverified** — check if `model` in frontmatter is honoured |

---

## 8. Parallel execution guidelines

- Use one git worktree per parallel agent (`isolation: "worktree"`).
- Cap concurrency at 3 unless approved.
- Check for file overlap before starting. Overlapping tasks run sequentially.
- Each parallel agent gets an explicit file scope.
- Route to cheapest tier per task.
- Keep agent prompts short and stable for cache efficiency.
- This repo IS a git repository — parallel execution is supported.

---

## 9. Next steps

1. **Install Claude Code CLI** and record the version.
2. **Pin model IDs** — replace `<PIN: ...>` placeholders with actual model IDs from `claude` CLI or API docs.
3. **Run the two-turn cache test** in a fresh Claude Code session.
4. **Probe the TTL** — compare 5-min vs. 1-hour write costs for your platform and decide.
5. **Run one cycle:** `/plan` → `/implement` → `/test` → `/review` on a small task.
6. **Compare costs** — cache-read share and per-agent cost against baseline.
7. **Apply suggested changes** to `CLAUDE.md` (add §21 Cost & Delegation).
