#!/usr/bin/env bash
set -u

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG_FILE="${HOOK_LOG_FILE:-$ROOT/.claude/logs/operations.jsonl}"

hook=""
tool=""
files=""
result=""
detail=""
session=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hook)
      hook="${2:-}"
      shift 2
      ;;
    --tool)
      tool="${2:-}"
      shift 2
      ;;
    --files)
      files="${2:-}"
      shift 2
      ;;
    --result)
      result="${2:-}"
      shift 2
      ;;
    --detail)
      detail="${2:-}"
      shift 2
      ;;
    --session)
      session="${2:-}"
      shift 2
      ;;
    *)
      detail="${detail:+$detail }$1"
      shift
      ;;
  esac
done

INPUT_JSON="${HOOK_INPUT_JSON:-}"
if [[ -z "$INPUT_JSON" && ! -t 0 ]]; then
  INPUT_JSON="$(cat)"
fi

mkdir -p "$(dirname "$LOG_FILE")"

export HOOK_INPUT_JSON="$INPUT_JSON"
export HOOK_LOG_FILE_TARGET="$LOG_FILE"
export HOOK_LOG_CLI_HOOK="$hook"
export HOOK_LOG_CLI_TOOL="$tool"
export HOOK_LOG_CLI_FILES="$files"
export HOOK_LOG_CLI_RESULT="$result"
export HOOK_LOG_CLI_DETAIL="$detail"
export HOOK_LOG_CLI_SESSION="$session"

python3 - <<'PY'
import datetime as dt
import json
import os
from pathlib import Path

raw = os.environ.get("HOOK_INPUT_JSON", "").strip()
data = {}
if raw:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}


def first(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


tool_input = data.get("tool_input") or {}
tool_response = data.get("tool_response") or {}

file_value = first(
    os.environ.get("HOOK_LOG_CLI_FILES"),
    tool_response.get("filePath"),
    tool_input.get("file_path"),
    tool_input.get("paths"),
)

if isinstance(tool_input.get("paths"), list) and not os.environ.get("HOOK_LOG_CLI_FILES"):
    file_value = ", ".join(str(item) for item in tool_input["paths"])

command_value = first(tool_input.get("command"), data.get("error"), tool_input.get("description"))
detail_value = first(os.environ.get("HOOK_LOG_CLI_DETAIL"), command_value, "hook fired")
if len(detail_value) > 500:
    detail_value = detail_value[:497] + "..."

record = {
    "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "hook": first(os.environ.get("HOOK_LOG_CLI_HOOK"), data.get("hook_event_name"), "unknown"),
    "tool": first(os.environ.get("HOOK_LOG_CLI_TOOL"), data.get("tool_name"), "unknown"),
    "files": file_value,
    "result": first(os.environ.get("HOOK_LOG_CLI_RESULT"), "info"),
    "detail": detail_value,
    "session_id": first(os.environ.get("HOOK_LOG_CLI_SESSION"), data.get("session_id")),
    "cwd": first(data.get("cwd"), os.getcwd()),
}

log_path = Path(os.environ["HOOK_LOG_FILE_TARGET"])
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as fh:
    json.dump(record, fh, ensure_ascii=False)
    fh.write("\n")
PY

exit 0
