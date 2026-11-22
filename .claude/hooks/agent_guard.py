"""PreToolUse guard for the Agent tool: logs every spawn and blocks expensive
model overrides outside the agents allowed to use them. Fails open on bad input."""
import datetime, json, os, sys

ALLOW_EXPENSIVE = {"architect", "planner", "opus-consultant"}
EXPENSIVE = ("opus", "fable")

raw = sys.stdin.read()
try:
    event = json.loads(raw)
except ValueError:
    sys.exit(0)

tool_input = event.get("tool_input") or {}
agent = str(tool_input.get("subagent_type") or tool_input.get("agent_type") or "").strip()
model = str(tool_input.get("model") or "").strip().lower()
blocked = bool(model) and any(m in model for m in EXPENSIVE) and agent not in ALLOW_EXPENSIVE

root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or "."
try:
    with open(os.path.join(root, ".claude", "agent-calls.jsonl"), "a", encoding="utf-8") as log:
        log.write(json.dumps({
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "session": event.get("session_id"),
            "agent": agent or None,
            "model": model or None,
            "blocked": blocked,
            "tool_input_keys": sorted(tool_input.keys()),
            "description": tool_input.get("description"),
        }) + "\n")
except OSError:
    pass

if blocked:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"Model '{model}' is reserved for {', '.join(sorted(ALLOW_EXPENSIVE))}. "
            f"Run '{agent or 'this agent'}' without a model override, "
            "or use /consult-opus for a design question."),
    }}))
sys.exit(0)
