#!/usr/bin/env bash
set -euo pipefail

MODE="test"
if [[ "${1:-}" == "--format-only" ]]; then
  MODE="format"
  shift
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG_SCRIPT="$ROOT/scripts/hooks/log_operation.sh"
INPUT_JSON="${HOOK_INPUT_JSON:-}"

if [[ -z "$INPUT_JSON" && ! -t 0 ]]; then
  INPUT_JSON="$(cat)"
fi

export HOOK_INPUT_JSON="$INPUT_JSON"
export HOOK_PROJECT_ROOT="$ROOT"

resolve_python() {
  local candidate
  for candidate in "$ROOT/venv/bin/python" "$ROOT/.venv/bin/python"; do
    if [[ -x "$candidate" ]] && "$candidate" -V >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v python3 >/dev/null 2>&1 && python3 -V >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1 && python -V >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

resolve_black() {
  local candidate
  for candidate in "$ROOT/venv/bin/black" "$ROOT/.venv/bin/black"; do
    if [[ -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v black >/dev/null 2>&1 && black --version >/dev/null 2>&1; then
    command -v black
    return 0
  fi
  return 1
}

FILE_PATH="$(python3 - <<'PY'
import json
import os
import sys

raw = os.environ.get("HOOK_INPUT_JSON", "")
data = json.loads(raw) if raw else {}
file_path = (data.get("tool_response") or {}).get("filePath") or (data.get("tool_input") or {}).get("file_path") or ""
print(file_path)
PY
)"

if [[ -z "$FILE_PATH" || "${FILE_PATH##*.}" != "py" ]]; then
  exit 0
fi

PYTHON_BIN="$(resolve_python)"

if [[ "$MODE" == "format" ]]; then
  if BLACK_BIN="$(resolve_black 2>/dev/null)"; then
    if "$BLACK_BIN" "$FILE_PATH" >/dev/null 2>&1; then
      HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result success --files "$FILE_PATH" --detail "black 自动格式化完成"
    else
      HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result failed --files "$FILE_PATH" --detail "black 自动格式化失败"
      echo "⚠️ black 自动格式化失败: $FILE_PATH" >&2
    fi
  else
    HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result skipped --files "$FILE_PATH" --detail "未找到 black，跳过自动格式化"
  fi
  exit 0
fi

TEST_TARGETS=()
TEST_OUTPUT="$(python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["HOOK_PROJECT_ROOT"]).resolve()
raw = os.environ.get("HOOK_INPUT_JSON", "")
data = json.loads(raw) if raw else {}
file_path = Path((data.get("tool_response") or {}).get("filePath") or (data.get("tool_input") or {}).get("file_path") or "")
if not file_path:
    raise SystemExit(0)
if not file_path.is_absolute():
    file_path = (root / file_path).resolve()
else:
    file_path = file_path.resolve()

if file_path.name.startswith("test_"):
    try:
        print(file_path.relative_to(root).as_posix())
    except ValueError:
        print(file_path.as_posix())
    raise SystemExit(0)

module_rel = ""
try:
    module_rel = file_path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
except ValueError:
    module_rel = file_path.with_suffix("").as_posix().replace("/", ".")

stem = file_path.stem
variants = {stem}
for suffix in ("_node", "_service", "_engine", "_client", "_fetcher", "_validator", "_generator", "_schema", "_schemas"):
    if stem.endswith(suffix):
        variants.add(stem[: -len(suffix)])
parts = [part for part in stem.split("_") if part]
if len(parts) >= 2:
    variants.add("_".join(parts[:2]))

candidates = []
for path in root.rglob("test*.py"):
    if any(part in {"venv", ".venv", ".git", ".omx", "__pycache__"} for part in path.parts):
        continue
    score = 0
    name = path.name
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""

    for variant in variants:
        if not variant:
            continue
        if name == f"test_{variant}.py":
            score += 6
        elif variant in name:
            score += 3
        if variant in text:
            score += 1

    if module_rel and module_rel in text:
        score += 5

    if score:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.as_posix()
        candidates.append((score, rel))

seen = set()
for _, rel in sorted(candidates, key=lambda item: (-item[0], item[1]))[:8]:
    if rel not in seen:
        seen.add(rel)
        print(rel)
PY
)"
while IFS= read -r target; do
  [[ -n "$target" ]] && TEST_TARGETS+=("$target")
done <<< "$TEST_OUTPUT"

if [[ ${#TEST_TARGETS[@]} -eq 0 ]]; then
  if [[ -d "$ROOT/tests" ]]; then
    TEST_TARGETS+=("tests")
  fi
  ROOT_LEVEL_TESTS="$(find "$ROOT" -maxdepth 1 -type f -name 'test_*.py' | sort || true)"
  while IFS= read -r test_file; do
    [[ -z "$test_file" ]] && continue
    TEST_TARGETS+=("$(basename "$test_file")")
  done <<< "$ROOT_LEVEL_TESTS"
fi

if [[ ${#TEST_TARGETS[@]} -eq 0 ]]; then
  HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result skipped --files "$FILE_PATH" --detail "未找到可执行测试目标"
  exit 0
fi

TEST_SUMMARY="$(printf '%s, ' "${TEST_TARGETS[@]}")"
TEST_SUMMARY="${TEST_SUMMARY%, }"

set +e
"$PYTHON_BIN" -m pytest "${TEST_TARGETS[@]}" -q --tb=short -x
TEST_STATUS=$?
set -e

if [[ $TEST_STATUS -eq 0 ]]; then
  HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result success --files "$FILE_PATH" --detail "关联测试通过: $TEST_SUMMARY"
  exit 0
fi

HOOK_INPUT_JSON="$INPUT_JSON" "$LOG_SCRIPT" --result failed --files "$FILE_PATH" --detail "关联测试失败: $TEST_SUMMARY"
echo "❌ 关联测试失败: $TEST_SUMMARY" >&2
exit 2
