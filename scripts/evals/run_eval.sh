#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ "${SKIP_DEEPEVAL:-0}" =~ ^(1|true|yes|on)$ ]]; then
  echo "[deepeval] SKIP_DEEPEVAL 已开启，跳过评测。"
  exit 0
fi

pick_python() {
  local candidates=()
  [[ -n "${PYTHON_BIN:-}" ]] && candidates+=("${PYTHON_BIN}")
  candidates+=(
    "$ROOT_DIR/.venv/bin/python"
    "$ROOT_DIR/venv/bin/python"
    "$(command -v python3 2>/dev/null || true)"
    "$(command -v python 2>/dev/null || true)"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    [[ -x "$candidate" ]] || continue
    if "$candidate" -c 'import sys; print(sys.version)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "未找到可用 Python 解释器。请设置 PYTHON_BIN 或安装 python3。" >&2
  return 1
}

PYTHON_BIN="$(pick_python)"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
export DEEPEVAL_USE_PROJECT_LLM="${DEEPEVAL_USE_PROJECT_LLM:-1}"
export PYTEST_ADDOPTS="--no-cov -m evaluation ${PYTEST_ADDOPTS:-}"

check_provider() {
  "$PYTHON_BIN" - <<'PY'
from app.core.config import get_settings
settings = get_settings()
if not any([
    settings.openai_api_key,
    settings.deepseek_api_key,
    settings.anthropic_api_key,
    settings.qianfan_api_key,
    settings.moonshot_api_key,
]):
    raise SystemExit(
        "未检测到可用的 LLM Provider Key。请配置 OPENAI_API_KEY / DEEPSEEK_API_KEY / "
        "ANTHROPIC_API_KEY / QIANFAN_API_KEY / MOONSHOT_API_KEY 之一。"
    )
print("Provider configuration detected.")
PY
}

ensure_deps() {
  "$PYTHON_BIN" - <<'PY'
import importlib.util
import sys
mods = ["deepeval", "pytest", "fastapi", "langgraph"]
missing = [name for name in mods if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("missing:" + ",".join(missing))
PY
}

if ! ensure_deps >/dev/null 2>&1; then
  echo "[deepeval] 安装评测依赖..."
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r requirements.txt -r requirements-test.txt "deepeval>=3.7.4,<4.0"
fi

check_provider

DEEPEVAL_IDENTIFIER="${DEEPEVAL_IDENTIFIER:-local-$(date +%Y%m%d-%H%M%S)}"
DISPLAY_MODE="${DEEPEVAL_DISPLAY:-failing}"
PARALLELISM="${DEEPEVAL_NUM_PROCESSES:-1}"
USE_CACHE="${DEEPEVAL_USE_CACHE:-0}"

cmd=("$PYTHON_BIN" -m deepeval test run tests/evaluation -d "$DISPLAY_MODE" -n "$PARALLELISM" -id "$DEEPEVAL_IDENTIFIER")
if [[ "$USE_CACHE" =~ ^(1|true|yes|on)$ ]]; then
  cmd+=("-c")
fi

printf '[deepeval] running:'
printf ' %q' "${cmd[@]}"
printf '\n'
"${cmd[@]}"
