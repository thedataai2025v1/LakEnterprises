# Task: Set up Claude Code cost governance, prompt caching, model routing and parallel execution

You are configuring this repository's `.claude/` folder and related markdown so that prompt caching is active and verified, routine work runs on cheaper models, heavy reasoning runs on Opus, subagent cost is controlled, and independent work runs in parallel. Work in phases and report at the end. Do not change application code.

## Protected files (read first, never edit)

Any file named `CLAUDE.md` or `SKILLS.md` (any letter case) anywhere in the project is protected:
- Do not edit, rename, overwrite, append to, or back up-and-replace these files.
- You may read them to inform suggestions.
- Do not create a `CLAUDE.md` in a folder that already has one. Do not create a `SKILLS.md`.
- If no root `CLAUDE.md` exists, create one using the spec in Phase 3. If it exists, leave it alone.

Find them with:
```bash
find . \( -iname 'CLAUDE.md' -o -iname 'SKILLS.md' \) -not -path '*/node_modules/*' -not -path '*/.git/*'
```

## Phase 0: Inspect before changing anything

1. Detect the environment:
   - OS and shell (Windows with Git Bash, macOS, or Linux). Hooks must use `bash` and POSIX-portable commands.
   - Whether this is a git repository (`git rev-parse --is-inside-work-tree`). If not, say so and ask before running `git init`.
   - Stack and commands: read `package.json`, `pyproject.toml`, `Makefile`, `README.md` and CI config. Record build, test, lint and type-check commands. Use `<TODO: command>` for anything unknown.
   - Claude Code version (`claude --version`). Record it. Caching, hook and subagent behaviour must be checked against this version.
   - Platform: whether Claude runs on Vertex AI or the first-party API. Record it, because the TTL and pricing differ.
2. Run the protected-file search. List each hit with its path and line count. Read them without changing them.
3. Inventory `.claude/`, `.gitignore`, and `scripts/claude_usage/`. Mark each as missing, matches spec, or differs.
4. Before changing an existing file that differs from spec, copy only that file to `.claude.bak-<YYYYMMDD-HHMM>/` with its original path. Never back up or touch protected files.
5. Report the inventory and plan (create, merge, keep) in a short table. Ask only if a step is hard to reverse.

## Phase 1: Prompt caching

Claude Code caches prompts by default. This phase makes the setup cache-friendly and verifies the cache works. It does not assume the TTL setting is honoured.

**1a. Keep the cached prefix stable.** The cache covers the start of each request: system prompt, tools, CLAUDE.md, rules, and agent definitions. Any change to that prefix invalidates the cache. Therefore:
- Do not add, remove or edit CLAUDE.md, rules, agents, skills or settings during a session. Make those changes between sessions.
- Do not add or remove MCP servers mid-session. Set them up before a session starts.
- Keep rules and agent descriptions short and stable, so the prefix is small and rarely changes.

**1b. Decide the TTL with a probe, not by default.** The 1-hour cache write costs more than the 5-minute default. Use it only if the measured saving on idle re-writes exceeds the extra write cost.
- Record the Vertex (or API) price for the 5-minute write, the 1-hour write and the cache read, for the model in use.
- If the 1-hour write is cheaper than the saved idle re-writes, set `CLAUDE_CODE_PROMPT_CACHE_TTL` to `1h` in `settings.json` `env`.
- Otherwise leave the key out, so the default applies, and record the decision.
- Until the probe is done, write the key as `<DECIDE: probe result>` and do not treat it as set.

**1c. Avoid cache-breaking defaults.**
- Use `opusplan` only if its model-switch cost is accepted. Record in the report that switching models mid-session can rewrite the cache. If the team wants fewer switches, use Sonnet as the default and reach Opus only through the Opus-tier agents.
- Do not set `autoMemoryEnabled` or persistent agent memory until they have been measured.

**1d. Verify caching works.** Do this in a fresh session, after the setup is written:
1. Send one short message. Note the input and cache-write tokens reported by `/cost`.
2. Send a second message within a minute. The second call should report cache-read tokens. If it reports none, caching is not working. Stop and report the failure with the Claude Code version and platform.
3. Record both results in the report.

**1e. Make cache health visible.** The `cost-report` skill must show the cache-read share of input tokens for the last 7 days. A drop after rollout means something is breaking the cache.

## Phase 2: Model routing and subagent cost controls

Every agent gets an explicit `model`. Tier map:

| Tier | Model | Use for |
|---|---|---|
| Opus | `opus` | Architecture, ADRs, plans, one narrow escalation question |
| Sonnet | `sonnet` | Code changes from a plan, tests, diff review |
| Haiku | `haiku` | Codebase search, log digests, summaries, wait and cost helpers |

Routing rules:
- Opus appears only on `architect`, `planner` and `opus-consultant`.
- `opus-consultant` has no `Agent` tool and no edit tools. It answers in 300 words or fewer.
- Pin full model IDs in `settings.json` `env` for Opus, Sonnet and Haiku. Use `<PIN: ...>` placeholders if unknown. Do not rely on the bare `sonnet` alias.
- Set `CLAUDE_CODE_SUBAGENT_MODEL` to `sonnet`.
- Do not switch models with `/model` mid-session unless the task needs it.

Subagent cost controls:
- **Return limits.** Every agent's instructions must end with a maximum return size:

  | Agent | Return limit |
  |---|---|
  | Explore | 150 words: file paths and line numbers, one line each |
  | log-triage | 30 lines: result, failing items with file:line, first error |
  | opus-consultant | 300 words |
  | implementer | 150 words: changed files and open issues |
  | test-engineer | 100 words: pass or fail plus the digest |
  | code-reviewer | Ranked findings list, no preamble |
  | planner | Plan file path only |
  | architect | ADR path plus a 50-word summary |

- **Per-run budgets.** Record a guideline for each agent type in the suggestions file: maximum tool calls per run (for example, Explore 10, implementer 120, code-reviewer 30). Exceeding a guideline is a signal to split the task, not an automatic failure.
- **Per-agent cost tracking.** `/cost-report` must break cost down by agent type if the usage data includes agent identity. If it does not, record "per-agent breakdown unavailable on this version" in the report.
- **Override name.** The built-in search agent is replaced only if its file is named exactly `Explore.md` and its frontmatter `name` is `Explore`. Check both.
- **Spawn depth.** Keep `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` at `2`. Mark it unverified until tested.
- **Log-triage repo rules.** Set `omitClaudeMd: true` on `log-triage` only. Mark it unverified until tested.

## Phase 3: Files to create or merge

**Root `CLAUDE.md`**: create only if missing. Spec: Stack, Commands, Conventions (two to five rules), Cost and delegation. Keep it under 150 lines. The Cost and delegation section must include: finish one task before starting another; keep a session for one topic; do not edit CLAUDE.md, rules or agents during a session; batch questions; use the named skills; use `log-triage` for long output; commit only after review and green tests.

**`.claude/rules/cost-and-delegation.md`**: create only when a root `CLAUDE.md` exists and is protected. Give it no `paths:` frontmatter so it applies everywhere. Include the same Cost and delegation rules. Flag in the report that unscoped rules must be verified to load every session.

**`.gitignore`** (root-anchored; merge, never remove existing rules):
```
/.claude/*
!/.claude/settings.json
!/.claude/agents/
!/.claude/skills/
!/.claude/rules/
!/.claude/hooks/
.claude/settings.local.json
.claude/transcripts/
```

**`.claude/settings.json`**: merge into existing JSON. Set `model`; `permissions.allow` for the project's lint, test, build, `git diff` and `git log` commands; `permissions.deny` for `.env*` reads, `rm -rf` and force push; `env` with pinned model IDs, `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` set to `2`, and the TTL key only as decided in Phase 1b; and a `PreToolUse` hook on matcher `Bash` running `bash .claude/hooks/pre-commit.sh`.

**Agents** (`.claude/agents/*.md`). Each needs `name`, a `description` containing "Delegate here" and its trigger, `model`, `effort`, `tools`, `maxTurns`, and a return limit in its instructions:

| File | Model | Effort | Tools | maxTurns | Extra |
|---|---|---|---|---|---|
| architect.md | opus | high | Read, Grep, Glob, Write | 40 | Return: ADR path plus 50 words |
| planner.md | opus | high | Read, Grep, Glob, Write | 40 | Return: plan path only |
| opus-consultant.md | opus | high | Read, Grep, Glob | 10 | Return: 300 words |
| implementer.md | sonnet | high | Read, Grep, Glob, Edit, Write, Bash, Agent(opus-consultant) | 120 | Return: 150 words |
| test-engineer.md | sonnet | high | Read, Grep, Glob, Edit, Write, Bash, Agent(opus-consultant) | 120 | Return: 100 words |
| code-reviewer.md | sonnet | high | Read, Grep, Glob, Bash (read-only git), Agent(opus-consultant) | 60 | Return: ranked list |
| log-triage.md | haiku | low | Read, Grep, Bash | 15 | `omitClaudeMd: true`; return: 30 lines |
| Explore.md | haiku | low | Read, Grep, Glob | 30 | Exact name `Explore`; return: 150 words |

Also create `_TEMPLATE.md` with the same frontmatter fields and a return-limit line. Existing agents outside this list are kept unchanged and noted in suggestions.

**Skills** (`.claude/skills/<name>/SKILL.md`). Use the exact file name `SKILL.md`:

| Skill | Mode | Target | Purpose |
|---|---|---|---|
| plan | fork | planner | Write `docs/plans/<topic>.md` |
| implement | fork | implementer | Execute an approved plan |
| test | fork | test-engineer | Targeted tests, digest only |
| review | fork | code-reviewer | Ranked findings on the diff |
| consult-opus | fork | opus-consultant | One narrow question |
| fix-issue | fork | implementer | Fix an issue, test, review, commit |
| pr-review | fork | code-reviewer | Review a PR by number |
| wait | inline, `model: haiku` | none | Background jobs, no polling over 270 s |
| cost-report | inline, `model: haiku` | none | Run `scripts/claude_usage/report.py`; show cost, cache-read share, and per-agent cost if available |

Forked skills use `context: fork` and an `agent:` field. Use `$ARGUMENTS` for input. Do not create skills the project does not need.

**Rules** (`.claude/rules/`): one file per area with distinct conventions, using `paths:` frontmatter. Keep each under 30 lines. Always create `tests.md`.

**`.claude/hooks/pre-commit.sh`**: read stdin. Exit 0 unless the Bash command contains `git commit`. If required tools are missing, exit 0 (fail open). Otherwise run type check, lint on staged files and tests with the project's real commands. Exit 2 with a message on failure. Run `bash -n` on it.

**`scripts/claude_usage/README.md`**: placeholder for the stdlib-only usage report. Do not write the script unless asked.

## Phase 4: Parallel execution

Parallel agents speed up development only for independent work.

- **Parallel:** different modules, separate test files, reviews of separate PRs, searches across different directories.
- **Sequential:** anything touching the same file, migration, lock file or config. Plan with `/plan`, then implement.
- Use one git worktree per parallel agent (`isolation: "worktree"`).
- Give each parallel agent a file scope and forbid edits outside it.
- Cap concurrency at 3 unless the user approves more.
- Route each parallel task to the cheapest tier that can do it.
- Check for file overlap before starting. Overlapping tasks run in sequence.
- If the repo is not git, run sequentially and say so.

Parallel work also affects caching: each agent has its own context, so keep agent prompts short and stable so their prefixes cache well.

## Phase 5: Verification

1. `settings.json` parses as JSON. Each agent has `name`, `description`, `model`, `tools` and `maxTurns`.
2. `opus` appears only on architect, planner and opus-consultant. opus-consultant has no `Agent` or edit tools.
3. `CLAUDE.md` (protected or created) and each rules file are 200 lines or fewer. Report line counts for protected files without changing them.
4. No secrets, project IDs or credentials in created files.
5. `bash -n .claude/hooks/pre-commit.sh` passes.
6. If git is available, `git status --ignored` shows only the intended tracked set.
7. The two-turn cache test from Phase 1d has run, and its result is recorded.
8. Each agent's instructions end with a return limit that matches the Phase 2 table.
9. `Explore.md` exists with `name: Explore`.
10. Each agent `description` contains "Delegate here" followed by its trigger.
11. `log-triage.md` has `omitClaudeMd: true`. Mark it unverified in the report.
12. `/cost-report` either shows per-agent cost or records that it is unavailable.
13. The suggestions file lists the per-run budget for each agent type.
14. List every `<PIN: ...>`, `<TODO: ...>` and `<DECIDE: ...>` placeholder.

## Phase 6: Suggestions file and report

Write `docs/claude-setup-suggestions.md`. This is the only place to propose changes to protected files. Include:

1. **Protected files found:** path, line count, and whether root or subfolder.
2. **Suggested changes to each `CLAUDE.md`:** missing sections, conflicts with the cost plan (such as auto-commit after every change), content that belongs in `.claude/rules/`, ready-to-paste Cost and delegation text, subfolder duplication of root rules, and the cache rule against editing CLAUDE.md, rules or agents during a session.
3. **Suggested changes to each `SKILLS.md`:** Claude Code loads `SKILL.md` inside `.claude/skills/<name>/`, not `SKILLS.md`. Suggest migrating its content with `name` and `description` frontmatter, and note any duplicates.
4. **Per-run budgets for each agent type**, as set in Phase 2.
5. **Suggested changes to other markdown:** agent descriptions that don't name a trigger, rules over 30 lines, and READMEs describing the old setup.

Then give a short chat report:
- Table of files created, merged, kept and backed up.
- Protected files found and confirmed untouched.
- Caching: TTL decision with its probe data, the two-turn test result, and the Claude Code version and platform.
- Model routing table.
- Subagent cost controls applied, and whether per-agent cost tracking is available.
- Parallel rules applied.
- Remaining placeholders.
- Items to verify on the pinned version: each `env` key, the TTL key, the `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` and `omitClaudeMd` keys, `Agent(...)` tool syntax, hook JSON format, whether unscoped rules load every session, and whether agent identity appears in usage data.
- Next steps: fill placeholders, run one `/plan` → `/implement` → `/test` → `/review` cycle on a small task, and compare cost per accepted task, cache-read share and per-agent cost against the baseline.

Do not claim a setting works until it has been tested. Mark unverified values as unverified.
