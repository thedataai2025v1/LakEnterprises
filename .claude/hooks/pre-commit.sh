#!/usr/bin/env bash
# pre-commit.sh — Claude Code PreToolUse hook for Bash(git commit)
# Reads the tool input from stdin. Exits 0 unless the command is a git commit.
# If it is a git commit, runs type check, lint, and tests first.
# Exits 2 with a message on failure. Fails open if tools are missing.

set -euo pipefail

# Read the tool input from stdin
INPUT=$(cat)

# Check if this is a git commit command
if ! echo "$INPUT" | grep -q "git commit"; then
  exit 0
fi

echo "Pre-commit hook: running checks before git commit..."

# Type check (fail open if mypy not found)
if command -v mypy &>/dev/null; then
  echo "Running mypy..."
  if ! mypy . --ignore-missing-imports 2>&1; then
    echo "ERROR: mypy type check failed. Fix type errors before committing." >&2
    exit 2
  fi
else
  echo "WARN: mypy not found, skipping type check"
fi

# Lint staged files (fail open if ruff not found)
if command -v ruff &>/dev/null; then
  echo "Running ruff check..."
  if ! ruff check . 2>&1; then
    echo "ERROR: ruff lint failed. Fix lint errors before committing." >&2
    exit 2
  fi
else
  echo "WARN: ruff not found, skipping lint"
fi

# Run tests (fail open if pytest not found)
if command -v python &>/dev/null && python -m pytest --version &>/dev/null 2>&1; then
  echo "Running tests..."
  if ! python -m pytest --tb=short -q 2>&1; then
    echo "ERROR: tests failed. Fix failing tests before committing." >&2
    exit 2
  fi
else
  echo "WARN: pytest not found, skipping tests"
fi

echo "All pre-commit checks passed."
exit 0
