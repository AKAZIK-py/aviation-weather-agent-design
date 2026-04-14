#!/usr/bin/env bash
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG_SCRIPT="$ROOT/scripts/hooks/log_operation.sh"
INPUT_JSON="${HOOK_INPUT_JSON:-}"

if [[ -z "$INPUT_JSON" && ! -t 0 ]]; then
  INPUT_JSON="$(cat)"
fi

if [[ "${HOOK_ALLOW_DANGEROUS_BASH:-0}" == "1" ]]; then
  HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result bypassed --detail "危险命令检查已由 HOOK_ALLOW_DANGEROUS_BASH=1 跳过"
  exit 0
fi

export HOOK_INPUT_JSON="$INPUT_JSON"
CHECK_RESULT="$(python3 - <<'PY'
import json
import os
import re
import shlex
import sys

raw = os.environ.get("HOOK_INPUT_JSON", "")
data = json.loads(raw) if raw else {}
cmd = (data.get("tool_input") or {}).get("command", "")
lower = cmd.lower()

reason = None

if ":(){ :|:& };:" in cmd:
    reason = "禁止执行 fork bomb。"
elif re.search(r"\b(curl|wget)\b[^\n|;]*\|\s*(sh|bash|zsh)\b", lower):
    reason = "禁止直接执行 curl|sh / wget|sh 管道命令。"
elif re.search(r"\b(shutdown|reboot|halt|poweroff)\b", lower):
    reason = "禁止执行会影响宿主机可用性的关机/重启命令。"
elif re.search(r"\bgit\s+reset\s+--hard\b", lower):
    reason = "禁止执行 git reset --hard。"
elif re.search(r"\bgit\s+clean\s+-f[dx]*", lower):
    reason = "禁止执行 git clean -fd/-fdx。"
elif re.search(r"\bgit\s+push\b[^\n;]*--force(?:-with-lease)?\b", lower):
    reason = "禁止执行强制推送。"
elif re.search(r"\b(mkfs(\.[a-z0-9]+)?|fdisk|sfdisk|parted)\b", lower):
    reason = "禁止执行磁盘分区/格式化命令。"
elif re.search(r"\bdd\b[^\n;]*\bof=/dev/", lower):
    reason = "禁止将 dd 输出写入块设备。"
elif re.search(r"\bfind\s+/\S*\s+-delete\b", lower):
    reason = "禁止在系统路径上执行 find -delete。"
else:
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    effective = tokens[:]
    if effective[:1] and effective[0] in {"sudo", "doas"}:
        effective = effective[1:]

    if effective[:1] and effective[0] == "rm":
        options = "".join(part[1:] for part in effective[1:] if part.startswith("-"))
        recursive = "r" in options.lower()
        targets = [part for part in effective[1:] if not part.startswith("-")]
        dangerous_targets = {
            "/",
            "/*",
            "~",
            "~/",
            "~/*",
            "$HOME",
            "$HOME/*",
            "${HOME}",
            "${HOME}/*",
            "*",
            "./*",
            "../*",
            ".",
            "..",
        }
        if recursive and any(target in dangerous_targets for target in targets):
            reason = "禁止递归删除根目录、家目录或通配范围。"
        elif recursive and any(target.startswith(prefix) for prefix in ("/etc", "/usr", "/bin", "/sbin", "/System", "/Library") for target in targets):
            reason = "禁止递归删除系统目录。"

    if reason is None and effective[:1] and effective[0] in {"chmod", "chown"}:
        opts = " ".join(effective[1:])
        if " -r " in f" {opts.lower()} " and any(path in lower for path in (" / ", " /etc", " /usr", " /bin", " /system", " /library")):
            reason = "禁止递归修改系统目录权限/属主。"

if reason:
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

HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result allowed --detail "Bash 命令通过危险命令检查"
exit 0
