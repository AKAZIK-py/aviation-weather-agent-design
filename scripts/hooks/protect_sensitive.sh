#!/usr/bin/env bash
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG_SCRIPT="$ROOT/scripts/hooks/log_operation.sh"
INPUT_JSON="${HOOK_INPUT_JSON:-}"

if [[ -z "$INPUT_JSON" && ! -t 0 ]]; then
  INPUT_JSON="$(cat)"
fi

if [[ "${HOOK_ALLOW_SENSITIVE_WRITE:-0}" == "1" ]]; then
  HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result bypassed --detail "敏感文件写保护已由 HOOK_ALLOW_SENSITIVE_WRITE=1 跳过"
  exit 0
fi

export HOOK_INPUT_JSON="$INPUT_JSON"
export HOOK_PROJECT_ROOT="$ROOT"
CHECK_RESULT="$(python3 - <<'PY'
import fnmatch
import json
import os
import sys
from pathlib import Path

raw = os.environ.get("HOOK_INPUT_JSON", "")
root = Path(os.environ.get("HOOK_PROJECT_ROOT", os.getcwd())).resolve()
data = json.loads(raw) if raw else {}
file_path = (data.get("tool_input") or {}).get("file_path", "")

if not file_path:
    sys.exit(1)

candidate = Path(file_path).resolve(strict=False)
try:
    relative = candidate.relative_to(root).as_posix()
except ValueError:
    relative = candidate.as_posix()

basename = candidate.name

allow_patterns = {
    ".env.example",
    ".claude/settings.json",
    ".pre-commit-config.yaml",
}
block_patterns = {
    ".env",
    ".env.*",
    ".git/*",
    ".git/**",
    ".claude/settings.local.json",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.crt",
    "*.cer",
    "*.der",
    "**/id_rsa",
    "**/id_rsa.pub",
    "**/id_ed25519",
    "**/id_ed25519.pub",
    "**/credentials*.json",
    "**/*secret*.json",
    "**/*token*.json",
}

def matches(patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(candidate.as_posix(), pattern):
            return pattern
    return None

if matches(allow_patterns):
    sys.exit(1)

matched = matches(block_patterns)
if matched:
    reason = f"敏感文件已锁定: {relative}（命中规则 {matched}）。如需覆盖，请显式设置 HOOK_ALLOW_SENSITIVE_WRITE=1。"
    payload = {
        "reason": reason,
        "decision": {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)

sys.exit(1)
PY
2>/dev/null || true)"

if [[ -n "$CHECK_RESULT" ]]; then
  REASON="$(printf '%s' "$CHECK_RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["reason"])')"
  DECISION_JSON="$(printf '%s' "$CHECK_RESULT" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["decision"], ensure_ascii=False))')"
  HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result blocked --detail "$REASON"
  printf '%s\n' "$DECISION_JSON"
  exit 0
fi

HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result allowed --detail "文件写入通过敏感文件保护检查"
exit 0
