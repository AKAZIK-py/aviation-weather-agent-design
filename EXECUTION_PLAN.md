# 航空气象Agent进化方案 — 执行计划

> 子代理 + Claude Code 并发执行，三层Hook架构
> 日期: 2026-04-14

---

## 一、全局架构总览

```
开发者工作流
│
├─ 写代码时 ────── Layer 1: 安全网 ──────────────────
│  ├─ PreToolUse hook: 拦截危险命令 (rm -rf, force push)
│  ├─ PreToolUse hook: 锁住敏感文件 (.env, credentials)
│  └─ PostToolUse hook: 自动格式化 (ruff format, prettier)
│
├─ 代码落地后 ──── Layer 2: 改后即测 ────────────────
│  ├─ PostToolUse hook: 改.py文件 → 自动跑关联测试
│  ├─ PR workflow: 强制全量测试通过才能merge
│  ├─ AI自查: Claude Code写完代码先 /review
│  └─ requesting-code-review skill: 独立reviewer subagent
│
└─ 提交前 ──────── Layer 3: 规范+日志 ───────────────
   ├─ pre-commit hook: ruff lint + mypy类型检查
   ├─ 操作日志: 每步操作写 .hermes/ops_log.jsonl
   └─ auto-commit: git diff → LLM生成规范commit message
```

---

## 二、三层Hook详细设计

### Layer 1: 安全网（拦截+保护+格式化）

#### 1.1 危险命令拦截

**配置位置**: `.claude/settings.json` → `PreToolUse` hooks

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "scripts/hooks/block_dangerous.sh"
          }
        ]
      }
    ]
  }
}
```

**`scripts/hooks/block_dangerous.sh`** 拦截规则:

| 模式 | 动作 | 原因 |
|------|------|------|
| `rm -rf /` | BLOCK | 灾难性删除 |
| `rm -rf *` | BLOCK | 通配删除 |
| `git push --force` (main/master) | BLOCK | 覆盖远端历史 |
| `git reset --hard` (有未提交修改) | BLOCK | 丢失工作区 |
| `:(){ :\|:& };:` | BLOCK | Fork炸弹 |
| `curl \| sh` / `curl \| bash` | BLOCK | 任意代码执行 |
| `chmod 777` | BLOCK | 过度权限 |
| `> /dev/sda` | BLOCK | 磁盘覆写 |

exit code 2 = 阻止执行并报错

#### 1.2 敏感文件锁定

**`scripts/hooks/protect_sensitive.sh`**:

| 文件/模式 | 动作 | 说明 |
|-----------|------|------|
| `.env`, `.env.*` | WARN + require确认 | API密钥 |
| `*.key`, `*.pem` | BLOCK | 私钥文件 |
| `credentials.json` | BLOCK | 认证凭据 |
| `.claude/settings.local.json` | WARN | 本地配置 |

实现方式: 在 PreToolUse hook 中检查 `$CLAUDE_FILE_PATHS`，命中敏感模式则 exit 2。

#### 1.3 自动格式化

**配置位置**: `.claude/settings.json` → `PostToolUse` hooks

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit(*.py)",
        "hooks": [
          {
            "type": "command",
            "command": "ruff format $CLAUDE_FILE_PATHS && ruff check --fix $CLAUDE_FILE_PATHS"
          }
        ]
      },
      {
        "matcher": "Write(*.py)",
        "hooks": [
          {
            "type": "command",
            "command": "ruff format $CLAUDE_FILE_PATHS && ruff check --fix $CLAUDE_FILE_PATHS"
          }
        ]
      }
    ]
  }
}
```

效果: Python文件每次被Edit或Write后，自动 `ruff format` + `ruff check --fix`。

---

### Layer 2: 改后即测（测试+自查+PR Gate）

#### 2.1 改后自动测试

**配置位置**: PostToolUse hook

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit(*.py)",
        "hooks": [
          {
            "type": "command",
            "command": "scripts/hooks/auto_test.sh $CLAUDE_FILE_PATHS"
          }
        ]
      }
    ]
  }
}
```

**`scripts/hooks/auto_test.sh`** 逻辑:

```bash
#!/bin/bash
# 输入: 被修改的文件路径
# 输出: exit 0 通过, exit 2 阻断

CHANGED_FILES="$*"

# 1. 映射源文件 → 测试文件
#    app/services/cache.py → tests/test_cache.py
#    app/nodes/parse_metar_node.py → tests/test_parse_metar.py
for f in $CHANGED_FILES; do
  TEST_FILE=$(echo "$f" | sed 's|^app/|tests/test_|')
  if [ -f "$TEST_FILE" ]; then
    python3 -m pytest "$TEST_FILE" -q --tb=short 2>&1
    if [ $? -ne 0 ]; then
      echo "❌ 测试失败: $TEST_FILE"
      exit 2  # 阻止继续
    fi
  fi
done

# 2. 如果没有找到映射测试文件，跑全量(采样)
python3 -m pytest tests/ -q --tb=short -x 2>&1
```

效果: 每次改完Python文件，自动跑对应的测试。测试失败 → 代码操作被阻断。

#### 2.2 AI自查机制

**Skill集成**: `requesting-code-review` skill

每次Claude Code完成一个任务后，调度流程：

```
Claude Code 完成任务
    ↓
Hermes 调用 requesting-code-review skill:
    Step 1: git diff --cached (获取变更)
    Step 2: 静态安全扫描 (secrets, injection, eval)
    Step 3: 基线测试对比 (新失败 vs 旧失败)
    Step 4: 自查清单
    Step 5: 独立reviewer subagent (delegate_task)
    Step 6: 评估结果
    Step 7: auto-fix循环 (最多2轮)
    Step 8: [verified] commit
```

关键设计: **独立reviewer** — 不是写代码的那个agent审查自己，而是用 `delegate_task` 启动一个全新上下文的subagent做review。

#### 2.3 PR强制测试

**Skill集成**: `github-pr-workflow` skill

**GitHub Actions workflow**: `.github/workflows/pr-gate.yml`

```yaml
name: PR Gate
on:
  pull_request:
    branches: [main, develop]

jobs:
  test-and-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-test.txt

      - name: Run tests (fail = block merge)
        run: python -m pytest tests/ -q --tb=short

      - name: Run lint (fail = block merge)
        run: ruff check . && mypy . --ignore-missing-imports

      - name: Run Golden Set eval (fail = block merge)
        run: deepeval test run tests/evaluation/ -q

      - name: Comment PR with results
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            // 把测试结果comment到PR上
```

**Branch protection rule**: `main` 和 `develop` 分支要求所有check通过才能merge。

---

### Layer 3: 规范+日志（Lint+Log+Auto-Commit）

#### 3.1 Git pre-commit hook

**位置**: `.git/hooks/pre-commit` 或 `pre-commit` 框架

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔍 Pre-commit checks..."

# 1. Lint
ruff check . --fix
if [ $? -ne 0 ]; then
  echo "❌ Ruff lint failed"
  exit 1
fi

# 2. Format check
ruff format --check .
if [ $? -ne 0 ]; then
  echo "⚠️ Auto-formatting..."
  ruff format .
  git add -A  # 重新暂存格式化后的文件
fi

# 3. Type check (仅对修改的文件)
CHANGED=$(git diff --cached --name-only -- '*.py')
if [ -n "$CHANGED" ]; then
  mypy $CHANGED --ignore-missing-imports
  if [ $? -ne 0 ]; then
    echo "❌ Type check failed"
    exit 1
  fi
fi

echo "✅ Pre-commit checks passed"
```

或用 `pre-commit` 框架:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

#### 3.2 操作日志系统

**`scripts/hooks/log_operation.sh`**:

```bash
#!/bin/bash
# 在每个hook点调用，记录操作日志

LOG_FILE=".hermes/ops_log.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOOK_TYPE="$1"        # PreToolUse, PostToolUse, pre-commit, etc.
TOOL_NAME="$2"        # Bash, Edit, Write, etc.
FILE_PATHS="$3"       # 受影响的文件
RESULT="$4"           # success, blocked, failed
DETAILS="$5"          # 额外信息

mkdir -p .hermes

echo "{\"ts\":\"$TIMESTAMP\",\"hook\":\"$HOOK_TYPE\",\"tool\":\"$TOOL_NAME\",\"files\":\"$FILE_PATHS\",\"result\":\"$RESULT\",\"detail\":\"$DETAILS\"}" >> "$LOG_FILE"
```

**日志格式** (JSONL, 每行一条):

```json
{"ts":"2026-04-14T13:45:00Z","hook":"PostToolUse","tool":"Edit","files":"app/services/cache.py","result":"success","detail":"ruff format applied"}
{"ts":"2026-04-14T13:45:05Z","hook":"PostToolUse","tool":"Edit","files":"app/services/cache.py","result":"success","detail":"auto_test: 3/3 passed"}
{"ts":"2026-04-14T13:46:00Z","hook":"pre-commit","tool":"git","files":"","result":"success","detail":"lint+format+typecheck passed"}
{"ts":"2026-04-14T13:46:05Z","hook":"auto-commit","tool":"claude","files":"app/services/cache.py,tests/test_cache.py","result":"success","detail":"feat: add TTL cleanup to cache service"}
```

**查看日志**:

```bash
# 最近20条操作
tail -20 .hermes/ops_log.jsonl | python3 -m json.tool

# 按hook类型统计
cat .hermes/ops_log.jsonl | python3 -c "
import sys, json
from collections import Counter
c = Counter(json.loads(l)['hook'] for l in sys.stdin)
for k,v in c.most_common(): print(f'{k}: {v}')
"

# 查看所有被阻断的操作
cat .hermes/ops_log.jsonl | python3 -c "
import sys, json
for l in sys.stdin:
    d = json.loads(l)
    if d['result'] in ('blocked','failed'):
        print(f\"{d['ts']} | {d['hook']} | {d['tool']} | {d['result']} | {d['detail']}\")
"
```

#### 3.3 Auto-Commit（LLM生成提交信息）

**方式一: Git hook + Claude Code print mode**

```bash
#!/bin/bash
# .git/hooks/prepare-commit-msg

# 如果不是merge或amend，用LLM生成commit message
if [ -z "$2" ]; then
  DIFF=$(git diff --cached --stat)
  CHANGED_FILES=$(git diff --cached --name-only)
  FULL_DIFF=$(git diff --cached | head -200)

  # 调用Claude Code生成commit message
  MSG=$(claude -p "根据以下变更生成一个conventional commit message（仅输出commit message，不要解释）:

文件变更:
$CHANGED_FILES

Diff统计:
$DIFF

Diff内容(前200行):
$FULL_DIFF" --max-turns 1 --output-format json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")

  if [ -n "$MSG" ]; then
    echo "$MSG" > "$1"
  fi
fi
```

**方式二: Hermes auto-commit skill (推荐)**

在Hermes中，完成任务后自动调用:

```python
# 工作流完成 → auto-commit
terminal(command="""
  DIFF=$(git diff --cached --stat)
  FILES=$(git diff --cached --name-only)
  if [ -n "$DIFF" ]; then
    claude -p "Generate a concise conventional commit message for these changes:\\n$FILES\\n$DIFF" \
      --max-turns 1 --allowedTools "Read" --bare
  fi
""", workdir="/path/to/project")
```

---

## 三、子代理 + Claude Code 并发执行方案

### 3.1 任务拆分与并发策略

基于 `EVOLUTION_PLAN.md` 的4个Phase，拆成可并发的独立任务:

```
Phase 1: 可观测性基础设施
├─ Task 1.1: 部署Langfuse (Docker)           ← Claude Code A
├─ Task 1.2: 集成Langfuse SDK到Agent         ← Claude Code B
├─ Task 1.3: 部署Prometheus+Grafana (Docker)  ← Claude Code C
├─ Task 1.4: 定义Prometheus指标              ← Claude Code D
└─ Task 1.5: 配置OTel Collector              ← 子代理 E

Phase 2: 自动化评测
├─ Task 2.1: 集成DeepEval + 评测用例          ← Claude Code F
├─ Task 2.2: pre-push hook                   ← 子代理 G
├─ Task 2.3: GitHub Actions PR gate          ← Claude Code H
└─ Task 2.4: Phoenix幻觉评测集成             ← 子代理 I

Phase 3: 记忆系统升级
├─ Task 3.1: SQLite FTS5语义记忆              ← Claude Code J
├─ Task 3.2: 自动摘要机制                    ← 子代理 K
├─ Task 3.3: 记忆注入prompt                  ← Claude Code L
└─ Task 3.4: 自动记忆提取                    ← 子代理 M

Phase 4: 告警+Hook系统
├─ Task 4.1: 三层Hook脚本编写                ← Claude Code N
├─ Task 4.2: AlertManager告警规则            ← 子代理 O
└─ Task 4.3: 端到端验证                     ← 主agent
```

### 3.2 并发执行模式

**使用 Claude Code skill 的 background 模式**:

```python
# 每个Claude Code实例用 background=true 并行跑
# 自带 notify_on_complete，完成后通知

# Claude Code A: 部署Langfuse
terminal(
    command="cd /Users/twzl/aviation-weather-projects && claude -p '在 aviation-weather-agent 项目中配置Langfuse自部署。创建 docker-compose.langfuse.yml 包含langfuse-server, postgres, redis。更新 .env 添加LANGFUSE配置。' --allowedTools 'Read,Write,Bash' --max-turns 20",
    background=True, notify_on_complete=True, timeout=600
)

# Claude Code B: 集成Langfuse SDK
terminal(
    command="cd /Users/twzl/aviation-weather-projects/aviation-weather-agent && claude -p '在 app/agent/graph.py 中集成Langfuse callback handler。修改 run_agent() 函数，在 config 中传入 langfuse_handler。确保每次Agent调用都被追踪。更新 requirements.txt。' --allowedTools 'Read,Edit,Bash' --max-turns 15",
    background=True, notify_on_complete=True, timeout=600
)

# Claude Code C: Prometheus+Grafana
terminal(
    command="cd /Users/twzl/aviation-weather-projects && claude -p '创建 docker-compose.monitoring.yml，包含Prometheus和Grafana。Prometheus scrape本机:8000/metrics。Grafana预置一个Agent监控Dashboard。' --allowedTools 'Read,Write,Bash' --max-turns 20",
    background=True, notify_on_complete=True, timeout=600
)
```

**使用 Hermes delegate_task 做评审类子代理**:

```python
# 子代理 E: 配置OTel Collector (偏配置/运维)
delegate_task(
    goal="配置OpenTelemetry Collector，接收来自Langfuse和应用的telemetry，分发到Prometheus",
    context="已有docker-compose.monitoring.yml。需要创建otel-collector-config.yml...",
    toolsets=["terminal", "file"]
)

# 子代理 G: pre-push hook
delegate_task(
    goal="创建 .git/hooks/pre-push 脚本，在push前运行deepeval评测",
    context="DeepEval已集成。需要写一个shell脚本...",
    toolsets=["terminal", "file"]
)
```

### 3.3 使用已有Skill辅助

| Skill | 用途 | 在哪个阶段 |
|-------|------|-----------|
| `requesting-code-review` | 每个Claude Code完成任务后自动review | 全阶段 |
| `subagent-driven-development` | 并发调度+两阶段review | Phase 1-4 |
| `test-driven-development` | Claude Code写代码时先写测试 | Phase 3 |
| `claude-code` | 并发编码任务 | 全阶段 |
| `github-pr-workflow` | PR创建+CI监控+自动merge | Phase 2 |
| `github-code-review` | PR review | Phase 2 |
| `systematic-debugging` | 测试失败时的调试 | 全阶段 |
| `aviation-agent-production` | 生产级模式参考 | Phase 1, 4 |

### 3.4 完整执行流程

```
Phase 1 启动 (并发5个任务)
│
├─ Claude Code A ──── Langfuse部署 ──────────────────┐
├─ Claude Code B ──── Langfuse SDK集成 ──────────────┤
├─ Claude Code C ──── Prometheus+Grafana ────────────┤  并行执行
├─ Claude Code D ──── Prometheus指标定义 ────────────┤  (~15分钟)
└─ 子代理 E ──────── OTel Collector配置 ─────────────┘
                                                      │
                                                      ▼
                                              全部完成后通知
                                                      │
    ┌─────────────────────────────────────────────────┘
    ▼
Phase 1 Review (独立reviewer subagent)
    ↓ 检查: 所有组件能启动? 指标能采集? Dashboard能显示?
    ↓ 通过 → Phase 2 启动
    ↓ 失败 → auto-fix循环 (最多2轮)
    │
Phase 2 启动 (并发4个任务)
    │
    ├─ Claude Code F ── DeepEval集成+评测用例 ───────┐
    ├─ 子代理 G ─────── pre-push hook ──────────────┤  并行
    ├─ Claude Code H ── GitHub Actions PR gate ─────┤  (~10分钟)
    └─ 子代理 I ─────── Phoenix集成 ─────────────────┘
                                                      │
                                                      ▼
                                              全部完成后通知
                                                      │
Phase 2 Review
    ↓
Phase 3 启动 (并发4个任务)
    │
    ├─ Claude Code J ── SQLite FTS5语义记忆 ─────────┐
    ├─ 子代理 K ─────── 自动摘要机制 ───────────────┤  并行
    ├─ Claude Code L ── 记忆注入prompt ─────────────┤  (~10分钟)
    └─ 子代理 M ─────── 自动记忆提取 ────────────────┘
                                                      │
Phase 3 Review
    ↓
Phase 4 启动 (并发3个任务)
    │
    ├─ Claude Code N ── 三层Hook脚本 ────────────────┐
    ├─ 子代理 O ─────── AlertManager规则 ────────────┤  并行
    └─ 主agent ──────── 端到端验证 ──────────────────┘
                                                      │
Phase 4 Review + 最终集成测试
    ↓
全部完成 → 更新EVOLUTION_PLAN.md进度 → commit
```

### 3.5 并发控制策略

**最大并发数**: 5个Claude Code实例 + 3个子代理 = 8个并行任务

**速率控制**:
- Claude Code实例间间隔2秒启动（避免API rate limit）
- 每个实例设 `--max-budget-usd 2.0`（成本上限）
- 超时设 `timeout=600`（10分钟自动kill）

**依赖管理**:
- Phase 1 内5个任务无依赖 → 并行
- Phase 2 依赖 Phase 1 完成 → 串行启动
- Phase 3 和 Phase 4 的Hook部分可部分重叠

**失败处理**:
- 单任务失败 → 不阻塞其他任务
- 全部完成后 → 主agent汇总失败任务，统一调度 fix subagent
- 最多重试2次

---

## 四、三层Hook配置文件清单

需要创建的文件:

```
aviation-weather-agent/
├── .claude/
│   ├── settings.json           ← Hook配置 (三层全配)
│   ├── settings.local.json     ← 个人覆盖 (gitignored)
│   ├── CLAUDE.md               ← 项目上下文
│   └── agents/
│       ├── security-reviewer.md  ← 安全审查agent
│       └── test-writer.md        ← 测试编写agent
├── .git/
│   └── hooks/
│       ├── pre-commit            ← Layer 3: lint+typecheck
│       ├── pre-push              ← Layer 2: 全量测试+评测
│       └── prepare-commit-msg    ← Layer 3: auto-commit message
├── .github/
│   └── workflows/
│       └── pr-gate.yml           ← PR强制测试
├── .pre-commit-config.yaml       ← pre-commit框架配置
├── scripts/
│   └── hooks/
│       ├── block_dangerous.sh    ← Layer 1: 危险命令拦截
│       ├── protect_sensitive.sh  ← Layer 1: 敏感文件保护
│       ├── auto_test.sh          ← Layer 2: 改后自动测试
│       ├── log_operation.sh      ← Layer 3: 操作日志
│       └── auto_commit.sh        ← Layer 3: LLM生成commit msg
├── .hermes/
│   └── ops_log.jsonl             ← 操作日志文件
└── docker-compose.monitoring.yml ← Prometheus+Grafana+Langfuse+OTel
```

---

## 五、skill调用矩阵

| 阶段 | 调用的Skill | 调用方式 | 并发 |
|------|------------|---------|------|
| Phase 1 | `claude-code` × 5 | background并行 | 5 |
| Phase 1 | `requesting-code-review` | 任务完成后 | 1 |
| Phase 2 | `claude-code` × 3 + `delegate_task` × 1 | background并行 | 4 |
| Phase 2 | `test-driven-development` | 指导写测试 | - |
| Phase 2 | `github-pr-workflow` | 创建PR+监控CI | 1 |
| Phase 3 | `claude-code` × 2 + `delegate_task` × 2 | background并行 | 4 |
| Phase 3 | `test-driven-development` | TDD写记忆测试 | - |
| Phase 4 | `claude-code` × 1 + `delegate_task` × 1 | 并行 | 2 |
| 全阶段 | `requesting-code-review` | 每个任务后review | 1 |
| 全阶段 | `systematic-debugging` | 测试失败时 | - |
| 全阶段 | `aviation-agent-production` | 参考生产模式 | - |

---

## 六、预计耗时

| 阶段 | 串行耗时 | 并发耗时 | 任务数 |
|------|---------|---------|--------|
| Phase 1 可观测性 | ~2h | ~30min | 5 |
| Phase 2 评测 | ~1.5h | ~20min | 4 |
| Phase 3 记忆 | ~1.5h | ~20min | 4 |
| Phase 4 Hook+告警 | ~1h | ~15min | 3 |
| Review + 修复 | ~1h | ~30min | 4轮 |
| **总计** | **~7h** | **~2h** | **16个任务** |

---

## 七、执行前检查清单

- [ ] `claude` CLI已安装 (`npm install -g @anthropic-ai/claude-code`)
- [ ] `claude auth status` 正常
- [ ] `ruff` 已安装 (`pip install ruff`)
- [ ] `mypy` 已安装 (`pip install mypy`)
- [ ] `deepeval` 已安装 (`pip install deepeval`)
- [ ] `docker compose` 可用
- [ ] `gh` CLI已安装 (GitHub操作)
- [ ] `git` hooks目录可写
- [ ] 项目在 `/Users/twzl/aviation-weather-projects/aviation-weather-agent`
