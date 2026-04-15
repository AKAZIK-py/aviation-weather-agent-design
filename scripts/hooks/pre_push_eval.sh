#!/usr/bin/env bash
# Pre-push hook: 跑 L1 标准集 + L2 badcase 回归，全过才允许 push
# 使用 run_eval.py 标准评测 Runner
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[eval]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[eval]${NC} $*"; }
log_error() { echo -e "${RED}[eval]${NC} $*"; }

# 允许跳过
if [[ "${SKIP_EVAL:-0}" =~ ^(1|true|yes|on)$ ]]; then
  log_warn "SKIP_EVAL 已开启，跳过评测。"
  exit 0
fi

# 查找 Python
pick_python() {
  local candidates=()
  [[ -n "${PYTHON_BIN:-}" ]] && candidates+=("${PYTHON_BIN}")
  candidates+=(
    "$ROOT_DIR/.venv/bin/python"
    "$ROOT_DIR/venv/bin/python"
    "$(command -v python3 2>/dev/null || true)"
    "$(command -v python 2>/dev/null || true)"
  )
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if "$candidate" -c 'import sys; print(sys.version)' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  log_error "未找到可用 Python 解释器。"
  return 1
}

PYTHON_BIN="$(pick_python)"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

log_info "========================================="
log_info " Pre-push 评测开始 (run_eval.py)"
log_info "========================================="

# L1: 标准集评测 (limit 5 作为 pre-push 快速检查)
log_info "L1 标准集抽样评测 (5 条)..."
L1_RESULT=0
"$PYTHON_BIN" scripts/evals/run_eval.py --mode direct --limit 5 --timeout 30 2>&1 | tail -20 || L1_RESULT=$?

if [[ $L1_RESULT -ne 0 ]]; then
  log_error "L1 标准集评测失败"
  log_error "设置 SKIP_EVAL=1 可跳过"
  exit 1
fi

# L2: badcase 回归
log_info "L2 badcase 回归检查..."
L2_RESULT=0
"$PYTHON_BIN" scripts/evals/run_eval.py --regression --timeout 30 2>&1 | tail -10 || L2_RESULT=$?

# L2 允许无 badcase 时通过
if [[ $L2_RESULT -ne 0 ]]; then
  BADCASE_DIR="$ROOT_DIR/eval/badcases"
  BC_COUNT=$(find "$BADCASE_DIR" -name 'BC_*.json' 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$BC_COUNT" -eq 0 ]]; then
    log_info "无 badcase 记录，L2 跳过"
  else
    log_error "L2 badcase 回归失败"
    exit 1
  fi
fi

log_info "========================================="
log_info " 全部评测通过，允许 push"
log_info "========================================="
exit 0
