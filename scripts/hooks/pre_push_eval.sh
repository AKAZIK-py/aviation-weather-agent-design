#!/usr/bin/env bash
# Pre-push hook: 跑 L1 标准集 + L2 抽样，全过才允许 push
# 安装方式: ln -sf ../../scripts/hooks/pre_push_eval.sh .git/hooks/pre-push
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
    [[ -x "$candidate" ]] || continue
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

# 结果目录
RESULT_DIR="$ROOT_DIR/eval/results"
mkdir -p "$RESULT_DIR"
RUN_ID="$(date +%Y-%m-%d)_run$(printf '%02d' $((RANDOM % 100)))"
RESULT_FILE="$RESULT_DIR/eval_${RUN_ID}.json"

# L1 标准集评测
run_l1_standard() {
  log_info "========== L1 标准集评测 =========="
  local dataset="$ROOT_DIR/eval/datasets/standard_testset_v1.json"
  if [[ ! -f "$dataset" ]]; then
    log_error "标准集文件不存在: $dataset"
    return 1
  fi

  local total
  total=$("$PYTHON_BIN" -c "import json; d=json.load(open('$dataset')); print(len(d['cases']))")
  log_info "标准集共 ${total} 条用例"

  # 运行 pytest 评测 (使用现有 evaluation 测试)
  local l1_result=0
  if [[ -f "$ROOT_DIR/tests/evaluation/test_hallucination_rate.py" ]]; then
    log_info "运行 L1 评测测试..."
    "$PYTHON_BIN" -m pytest tests/evaluation/ \
      -x --tb=short -q \
      --no-header \
      -p no:cacheprovider \
      2>&1 | tail -20 || l1_result=$?
  else
    log_warn "未找到评测测试文件，使用基础检查代替"
    # 基础检查: 数据集格式是否合法
    "$PYTHON_BIN" -c "
import json, sys
try:
    d = json.load(open('$dataset'))
    cases = d.get('cases', [])
    assert len(cases) > 0, '数据集为空'
    for c in cases:
        assert 'id' in c, f'缺少 id: {c}'
        assert 'metar' in c, f'{c[\"id\"]}: 缺少 metar'
        assert 'role' in c, f'{c[\"id\"]}: 缺少 role'
        assert 'query' in c, f'{c[\"id\"]}: 缺少 query'
        assert 'expected_key_info' in c, f'{c[\"id\"]}: 缺少 expected_key_info'
        assert 'scoring_criteria' in c, f'{c[\"id\"]}: 缺少 scoring_criteria'
    print(f'L1 数据集格式检查通过: {len(cases)} 条')
except Exception as e:
    print(f'L1 数据集检查失败: {e}', file=sys.stderr)
    sys.exit(1)
" || l1_result=$?
  fi

  if [[ $l1_result -ne 0 ]]; then
    log_error "L1 标准集评测失败"
    return 1
  fi
  log_info "L1 标准集评测通过"
  return 0
}

# L2 抽样评测 (从 badcases 回归)
run_l2_sample() {
  log_info "========== L2 抽样评测 =========="
  local badcase_dir="$ROOT_DIR/eval/badcases"
  local bc_count
  bc_count=$(find "$badcase_dir" -name 'BC_*.json' 2>/dev/null | wc -l | tr -d ' ')

  if [[ "$bc_count" -eq 0 ]]; then
    log_info "无 badcase 记录，L2 跳过"
    return 0
  fi

  log_info "发现 ${bc_count} 条 badcase 记录"
  # 抽样评测: 随机取最多 10 条
  local sample_size=$(( bc_count < 10 ? bc_count : 10 ))
  log_info "抽样 ${sample_size} 条进行回归检查"

  # 基础检查: badcase 格式是否合法
  "$PYTHON_BIN" -c "
import json, glob, sys, os

schema_path = '$badcase_dir/schema.json'
files = glob.glob('$badcase_dir/BC_*.json')
if not files:
    print('无 badcase 文件，跳过')
    sys.exit(0)

errors = 0
for f in sorted(files)[:10]:
    try:
        data = json.load(open(f))
        # 检查必填字段
        for field in ['case_id', 'category', 'timestamp', 'input', 'expected', 'actual']:
            if field not in data:
                print(f'{os.path.basename(f)}: 缺少必填字段 {field}')
                errors += 1
                continue
        # 检查分类是否合法
        valid_cats = ['task_not_finished', 'critical_info_missed', 'output_too_template', 'hallucination', 'other']
        if data.get('category') not in valid_cats:
            print(f'{os.path.basename(f)}: 无效分类 {data.get(\"category\")}')
            errors += 1
        # 未修复的数量
        if not data.get('fixed', False):
            print(f'{os.path.basename(f)}: 未修复 (category={data.get(\"category\")})')
            errors += 1
    except Exception as e:
        print(f'{os.path.basename(f)}: 解析失败 {e}')
        errors += 1

if errors > 0:
    print(f'L2 回归检查: {errors} 个问题', file=sys.stderr)
    sys.exit(1)
print('L2 badcase 回归检查通过')
" && return 0

  log_error "L2 抽样评测失败"
  return 1
}

# 写入评测结果
write_result() {
  local status="$1"
  local l1="$2"
  local l2="$3"
  "$PYTHON_BIN" -c "
import json
from datetime import datetime
result = {
    'run_id': '$RUN_ID',
    'timestamp': datetime.now().isoformat(),
    'status': '$status',
    'l1_standard': {'passed': $l1, 'dataset': 'standard_testset_v1.json'},
    'l2_badcase': {'passed': $l2, 'note': 'badcase regression'},
    'allow_push': '$status' == 'pass'
}
with open('$RESULT_FILE', 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print('评测结果已写入: $RESULT_FILE')
"
}

# 主流程
main() {
  log_info "========================================="
  log_info " Pre-push 评测开始"
  log_info "========================================="

  local l1_pass=0
  local l2_pass=0

  if run_l1_standard; then
    l1_pass=1
  fi

  if run_l2_sample; then
    l2_pass=1
  fi

  if [[ $l1_pass -eq 1 && $l2_pass -eq 1 ]]; then
    write_result "pass" "$l1_pass" "$l2_pass"
    log_info "========================================="
    log_info " 全部评测通过，允许 push"
    log_info "========================================="
    exit 0
  else
    write_result "fail" "$l1_pass" "$l2_pass"
    log_error "========================================="
    log_error " 评测失败，拒绝 push"
    log_error " L1 标准集: $([ $l1_pass -eq 1 ] && echo '通过' || echo '失败')"
    log_error " L2 回归:   $([ $l2_pass -eq 1 ] && echo '通过' || echo '失败')"
    log_error " 请修复后重试，或设置 SKIP_EVAL=1 跳过"
    log_error "========================================="
    exit 1
  fi
}

main "$@"
