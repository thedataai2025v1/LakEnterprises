# Git / GitHub Workflow Guide

> **Project:** LakEnterprises — AI-powered enterprise process automation
> **GitHub:** <https://github.com/thedataai2025v1/LakEnterprises>
> **Format:** Markdown — render with any Markdown viewer
> **Stack:** Python 3.12, LangChain, LangGraph
> **Guide based on:** samples/Git_GitHub_Workflow_Guide.html (adapted for LakEnterprises)

---

## 1. Branch model

**Type:** Trunk-based (3 permanent branches + short-lived feature branches)

### Permanent branches

| **Branch** | **Purpose** | **Who merges here** | **What it represents** |
|---|---|---|---|
| `development` | Integration branch for active work | Contributors, via a PR from `feature/*` or `bugfix/*` | Dev / integration. Not a production deploy. |
| `testing` | QA and staging validation | Release owner | Staging. Apply still needs a reviewed plan. |
| `main` | Code that is allowed to ship | Release owner | Production candidate. A merge is not itself a deploy. |

**Rules**

- Create every feature branch from an up-to-date `development`.
- Open every feature pull request into `development`. Do not open it into `testing` or `main`.
- Do not push commits directly to `development`, `testing`, or `main`.
- Do not stack a feature branch on another feature branch. If TASKS.md names a predecessor, merge that predecessor first.
- One sub-task in TASKS.md is one branch, one pull request, and one status change to `Completed ✅` after merge.
- A merge to `main` does not mean the cloud environment is deployed. MEMORY.md stays honest until a real apply has happened.

---

## 2. Before you start

### Access

- Use the GitHub account that owns <https://github.com/thedataai2025v1/LakEnterprises>. Collaborators need write access before they can push.
- Confirm the repository page loads. Check whether it has commits yet (a new repo may have none).
- Turn on two-factor authentication on the GitHub account.
- Prefer HTTPS with GitHub CLI, or SSH if you already have a key on the account. Do not put tokens in the repo.

### Tools to install

| **Tool** | **Version** | **Notes** |
|---|---|---|
| Git | 2.40+ | Git for Windows includes Git Bash. PowerShell is the shell used in this project. |
| GitHub CLI (gh) | Latest | Recommended for pull requests from the terminal. |
| Python | 3.12 | LangChain, LangGraph agents, pytest. Use `.venv\Scripts\python.exe`. |
| uv | Latest | Package manager / virtual environment tool. |
| Editor | Cursor or VS Code | Python extension, LangChain snippets. |

**Verify:**

```powershell
git --version
gh --version
python --version
uv --version
```

---

## 3. Create the three branches on GitHub

Run this once. After `development` is created, do not re-create it per feature.

```powershell
# 3a) Clone locally (if not done yet)
gh repo clone thedataai2025v1/LakEnterprises
cd LakEnterprises

# 3b) Create and push the permanent branches
git checkout -b development
git push -u origin development

git checkout -b testing
git push -u origin testing

# 3c) Return to main (default branch)
git checkout main
```

> If `main` does not exist yet (empty repo), create the first commit first:
> ```powershell
> git commit --allow-empty -m "Initial commit"
> git push -u origin main
> ```
> Then proceed with 3b.

---

## 4. Create a local mirror

Clone the repository to your working machine:

```powershell
# If not already cloned
gh repo clone thedataai2025v1/LakEnterprises
cd LakEnterprises

# Ensure all remote branches are tracked locally
git fetch --all
```

> **Why a mirror?** The local clone lets you work offline, draft commits, and review diffs before pushing. The canonical history lives on GitHub.

---

## 5. Work on a sub-task

> **This section is the daily workflow.** Read it in order each time you start a new sub-task.

### Step 1: Pick a sub-task

Open `TASKS.md` and find the next `Pending ❌` sub-task in execution order.

| **Field** | **Example** |
|---|---|
| Task | P2-1 · LangGraph core scaffold |
| Branch | `feature/langgraph-scaffold` |
| Depends on | P1-1 (must be merged first) |

> **Rule:** If a dependency is not yet merged into `development`, wait or work on an independent sub-task.

### Step 2: Create the branch

```powershell
# 2a) Make sure your local development is up to date
git checkout development
git pull origin development

# 2b) Create the feature branch from development
git checkout -b feature/langgraph-scaffold
```

### Step 3: Code

- Write code, tests, and documentation.
- Follow the conventions in `EURON.md` and `docs/02-hld.md`.
- Use the `.claude/` setup (prompt caching, agent guard) if working with Claude Code.
- **Do not** commit secrets, tokens, or API keys.
- **Do not** commit large binaries or generated files.

> **Security rule:** Sanitize any HTML output (SEC050). Use templates, not string concatenation. When inserting dynamic content into HTML, escape it or use a sanitizer (e.g., `bleach` for Python).

### Step 4: Commit

```powershell
git add .
git commit -m "P2-1: Add LangGraph core scaffold with agent base class"
```

> **Commit message format:** `P#-#`: Short description of the change. Include the phase and sub-task number from TASKS.md.

### Step 5: Push and open a pull request

```powershell
git push -u origin feature/langgraph-scaffold

# Open a PR into development (not main, not testing)
gh pr create --base development --title "P2-1: Add LangGraph core scaffold" --body "Implements sub-task P2-1 from TASKS.md. LangGraph core scaffold with agent base class."
```

### Step 6: Review and merge

- Review your own PR: check the diff, run the tests locally, verify the build.
- If a collaborator reviews, address their comments.
- When approved, merge into `development` (squash merge to keep history clean).

```powershell
gh pr merge --squash --delete-branch
```

### Step 7: Mark it complete

- In `TASKS.md`, change the status of the sub-task from `Pending ❌` to `Completed ✅`.
- Commit this change on `development`:

```powershell
git checkout development
git pull origin development
# Edit TASKS.md
git add TASKS.md
git commit -m "Mark P2-1 complete"
git push origin development
```

---

## 6. Release main

### Promotion path

```
development  ──(promote)──>  testing  ──(promote)──>  main
```

### How to promote `development` → `testing`

```powershell
git checkout testing
git pull origin testing
git merge --no-ff development -m "Promote development to testing"
git push origin testing
```

### How to promote `testing` → `main`

```powershell
git checkout main
git pull origin main
git merge --no-ff testing -m "Promote testing to main"
git push origin main
```

### Apply rules

| **Step** | **Rule** |
|---|---|
| 1. Development is stable | All active sub-tasks in the current phase pass tests. |
| 2. Promote to testing | Manual QA on staging. Run the full test suite. |
| 3. Promote to main | Only after testing passes. A merge is not a deploy — it marks code as shippable. |
| 4. Deploy | Follow the deploy plan in `docs/03-lld.md` (if any). Update `MEMORY.md` when a real apply happens. |

> **Never merge directly from `development` to `main`.** `testing` is the gate.

---

## 7. When something goes wrong

### A commit broke development

**Option A — Fix-forward** (preferred):

```powershell
git checkout development
git pull origin development
# Fix the bug
git commit -m "Fix: ..."
git push origin development
```

**Option B — Revert** (when the fix is non-trivial):

```powershell
git checkout development
git pull origin development
git revert <COMMIT_HASH>
git push origin development
```

> After a revert, open a new sub-task in TASKS.md to fix the issue properly.

### A merged PR broke testing or main

1. Revert on the branch where it broke:

```powershell
git checkout testing   # or main
git pull origin testing
git revert <COMMIT_HASH>
git push origin testing
```

2. Fix the issue on a new `feature/*` branch from `development`.
3. Re-promote when fixed.

---

## 8. Rules worth printing

| # | Rule |
|---|---|
| 1 | Every sub-task in TASKS.md is one branch (`feature/<name>`) and one PR into `development`. |
| 2 | Never push directly to `development`, `testing`, or `main`. |
| 3 | Never stack a feature branch on another feature branch. |
| 4 | A merge to `main` is not a deploy. `MEMORY.md` stays honest. |
| 5 | Sanitize all HTML output (SEC050). |
| 6 | Never commit secrets, tokens, or API keys. |
| 7 | Commit messages include the TASKS.md sub-task number (e.g., `P2-1`). |
| 8 | Sub-tasks in the same phase that do not share files can be worked on in parallel. |
| 9 | If you are blocked by something only the user can do, say exactly what, in one line. |
| 10 | After merge, mark the sub-task `Completed ✅` in TASKS.md. |

---

## 9. Appendix A: Git commands used in this guide

```powershell
# Clone
gh repo clone thedataai2025v1/LakEnterprises
cd LakEnterprises

# Create permanent branches
git checkout -b development
git push -u origin development

# Create a feature branch from development
git checkout development
git pull origin development
git checkout -b feature/<name>

# Commit and push
git add .
git commit -m "P#-#: Description"
git push -u origin feature/<name>

# Open a PR into development
gh pr create --base development --title "P#-#: Title" --body "Body"

# Merge PR (squash)
gh pr merge --squash --delete-branch

# Promote development → testing
git checkout testing
git merge --no-ff development -m "Promote development to testing"
git push origin testing

# Promote testing → main
git checkout main
git merge --no-ff testing -m "Promote testing to main"
git push origin main

# Revert a commit
git checkout <branch>
git revert <COMMIT_HASH>
git push origin <branch>
```

---

## 10. Appendix B: Pull-request checklist

Before merging any PR into `development`:

- [ ] The PR title matches the TASKS.md sub-task number and name.
- [ ] All tests pass locally (`pytest`).
- [ ] The code follows the conventions in `EURON.md` and `docs/02-hld.md`.
- [ ] No secrets, tokens, or API keys are committed.
- [ ] HTML output is sanitized (SEC050) if the sub-task touches HTML.
- [ ] `TASKS.md` is updated to mark the sub-task `Completed ✅` (done after merge).
- [ ] The PR targets `development`, not `testing` or `main`.

---

## 11. Appendix C: Memory and honesty

### MEMORY.md

- `MEMORY.md` (if it exists) records what has actually been deployed, not what has been merged.
- A merge to `main` means "ready to ship." A deploy means "running in production."
- Update `MEMORY.md` only when a real apply happens.

### TASKS.md

- `TASKS.md` is the execution order. It is updated after every merge.
- A sub-task moves from `Pending ❌` to `Completed ✅` only after its PR is merged and the branch is deleted.
- If a sub-task is abandoned, mark it `Skipped ⏭️` with a one-line reason.

---

*This guide is adapted from the CloudDesk Support project workflow (samples/Git_GitHub_Workflow_Guide.html) for the LakEnterprises project. Adjust tool versions and deploy steps as the project evolves.*