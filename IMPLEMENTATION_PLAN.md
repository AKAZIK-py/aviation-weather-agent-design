# 航空气象 Agent — 实施方案 v2.2（修订+验证版）

> 版本: v2.2 (Codex审核修订 + 全量评测验证)
> 日期: 2026-04-15 → 2026-04-16
> 架构: Agent=DeepSeek, Judge=Claude Code(辅助)/DeepSeek(降级)
> 状态: 已执行，全量评测通过

### Codex 审核修订记录 (v2.1 → v2.2)

| # | 问题 | 严重度 | 修订方案 | 状态 |
|---|------|--------|---------|------|
| 1 | 数据契约冲突(v1冻结 vs 扩充) | 严重 | v1冻结不动，v2独立新建，Runner兼容两种格式 | ✅ 已确认无冲突 |
| 2 | Runner 直 import 有副作用 | 严重 | 使用 importlib.deferred import + sys.path 修正(run_eval.py L30) | ✅ 已修复 |
| 3 | Judge 同模型自评 | 严重 | Judge降级为辅助指标，不入Gate判定；Claude Code不可用时跳过 | ✅ 已降级 |
| 4 | Badcase 沉淀太宽 | 严重 | infra_failure 不入库；Runner当前不自动调badcase_manager | ✅ 已过滤 |
| 5 | Langfuse 命令错 | 严重 | 待Langfuse部署时验证 | ⏳ 延后 |
| 6 | 基线评测放太晚 | 建议 | 全量评测已跑完(50+30+10=90条)，基线数据已获取 | ✅ 已完成 |

---

## 一、架构总览

```
评测Runner (scripts/evals/run_eval.py)
  ├── 模式1: 直调模式 (--mode direct)
  │   from app.agent.graph import run_agent
  │   适合: 快速开发调试
  │
  └── 模式2: API E2E模式 (--mode api)
      POST http://localhost:8000/api/v3/chat
      适合: 真实端到端评测（走FastAPI路由/校验/中间件）

打分引擎 (scripts/evals/scorer.py)
  ├── 脚本打分 (自动): 任务完成率 / 关键信息命中率 / 模板化检测
  └── Claude Code Judge (--judge): 输出可用率 / 幻觉率

产物目录 (eval/results/<run_id>/)
  ├── manifest.json        # 环境元数据
  ├── case_results.jsonl   # 逐条结果
  ├── summary.json         # 汇总指标
  ├── summary.md           # 可读报告
  └── badcases.jsonl       # 新增badcase
```

---

## 二、指标体系（最终版）

### 门禁指标（决定PASS/FAIL）

| 指标 | 定义 | 打分方式 | 目标 |
|------|------|---------|------|
| 任务完成率 | Agent有没有真正回答用户的问题，而不是只返回中间数据 | 脚本：检测输出是否包含结论性语句 | ≥80% |
| 关键信息命中率 | 当前角色最关心的信息是否被说到 | 脚本：逐条比对expected_key_info | ≥75% |
| 模板化率 | 是否还在套固定模板格式 | 脚本：检测旧版栏目+结构化特征 | ≤20% |
| badcase回归通过率 | 历史失败样本是否修复 | 脚本：重跑fixed=false的badcase | =100% |
| 安全类case | CRITICAL风险是否漏报 | 脚本：检查<1km能见度/雷暴/风切变 | =100% |

### 辅助指标（参考，不单独决定PASS/FAIL）

| 指标 | 定义 | 打分方式 | 说明 |
|------|------|---------|------|
| 输出可用率 | 能不能直接给角色用 | Claude Code Judge | 3个是/否问题 |
| 幻觉率 | 有没有编造数据/规则 | Claude Code Judge | 对比METAR原文+parsed结果 |
| 延迟P50/P95 | 端到端耗时 | 计时 | 确保没改慢 |
| Token消耗 | 成本 | 日志 | 监控用 |

### 砍掉的指标（不再评测）

| 原指标 | 为什么砍 |
|--------|---------|
| METAR解析准确率 | Agent调API拿到的是结构化JSON，不是让LLM解析文本，脚本验证无意义 |
| 飞行规则判断准确率 | 同上，规则函数的结果不取决于Agent |
| 工具调用准确率 | 归入任务完成率（如果完成了任务，工具调用自然是对的） |
| 上下文精度 | 记忆系统未成熟，评不了 |

---

## 三、PE架构优化（报告中体现）

### 实验式记录结构

| 实验 | PE版本 | 架构特征 | 保持不变 | 影响指标 | 实测变化 |
|------|--------|---------|---------|---------|---------|
| Baseline | V2 | 固定模板：CoT+JSON格式 | 模型/数据/温度 | 全部 | 待测 |
| Exp1 | V3 | 约束边界：identity+focus+forbidden+anti_template | 模型/数据/温度 | 模板化率↓ 可用率↑ | 待测 |

### V3 PE 改了4个部分

1. 砍掉CoT步骤链 → Agent自主决定思考路径
2. 砍掉固定输出格式 → LLM根据问题复杂度自适应
3. 加约束边界 → 每个角色定义"关注什么+不碰什么"
4. 加反模板化指令 → 每个角色专属anti_template

---

## 四、模型选型优化（报告中体现）

### 实验式记录结构

| 实验 | 配置变更 | 保持不变 | 影响指标 | 实测变化 |
|------|---------|---------|---------|---------|
| Baseline | 全局temperature=0.7 | PE/数据 | 全部 | 待测 |
| Exp1 | 温度按任务5档(0.0/0.0/0.3/0.7/0.0) | PE/数据 | 任务完成率↑ 精确性↑ | 待测 |
| Exp2 | Judge独立(Claude Code) | PE/数据/温度 | 幻觉检测准确率↑ | 待测 |

---

## 五、数据契约（v2）

### standard_testset_v2.json 结构

```json
{
  "metadata": {
    "version": "v2",
    "created": "2026-04-15",
    "total_cases": 50,
    "description": "标准评测集v2"
  },
  "cases": [
    {
      "id": "STD_001",
      "metar": "METAR ZSSS 140600Z 18012KT 0800 FG BKN002 12/11 Q1008",
      "parsed": {"visibility": 800, "cloud_base": 200, "weather": "FG"},
      "role": "pilot",
      "query": "虹桥机场天气怎么样",
      "expected_key_info": ["能见度800m", "有雾", "云底高200ft"],
      "expected_flight_rules": "LIFR",
      "scoring_criteria": {
        "must_mention": ["能见度", "云底高"],
        "must_give": ["进近建议"],
        "must_not_output": ["【风险分析】", "【建议措施】"]
      }
    }
  ]
}
```

关键点：
- `parsed` 字段：给 Judge 做幻觉判定的参考事实
- v1 冻结不动，新建 v2
- Runner 兼容 `{metadata,cases}` 和扁平数组两种格式

---

## 六、Runner 产物契约

### 输出目录: `eval/results/<run_id>/`

run_id = `run_<YYYYMMDD_HHMMSS>_<short_hash>`

### manifest.json

```json
{
  "run_id": "run_20260415_013000_a1b2",
  "timestamp": "2026-04-15T01:30:00Z",
  "commit": "e8038fb",
  "dataset_version": "v2",
  "dataset_path": "eval/datasets/standard_testset_v2.json",
  "model": "deepseek-chat",
  "provider": "deepseek",
  "mode": "api",
  "judge_enabled": true,
  "judge_model": "claude-code",
  "runner_version": "1.0.0",
  "total_cases": 50
}
```

### case_results.jsonl（每行一条）

```json
{"case_id":"STD_001","role":"pilot","status":"success","output":"...","latency_ms":2300,"tokens":450,"task_completed":true,"key_info_hit_rate":0.8,"is_template":false,"judge_usable":true,"judge_verbose":false,"judge_is_template":false,"error_type":null}
```

### summary.json

```json
{
  "total": 50, "success": 45, "infra_failures": 5,
  "task_completion_rate": 0.90,
  "key_info_hit_rate": 0.78,
  "template_rate": 0.12,
  "judge_usable_rate": 0.74,
  "hallucination_rate": 0.06,
  "badcase_regression_rate": null,
  "gate_passed": true,
  "gate_details": {
    "task_completion": {"value": 0.90, "threshold": 0.80, "passed": true},
    "key_info": {"value": 0.78, "threshold": 0.75, "passed": true},
    "template": {"value": 0.12, "threshold": 0.20, "passed": true}
  }
}
```

### summary.md（人类可读）

```markdown
# 评测报告 - run_20260415_013000_a1b2

## 门禁结果: ✅ PASS

| 指标 | 值 | 阈值 | 结果 |
|------|------|------|------|
| 任务完成率 | 90% | ≥80% | ✅ |
| 关键信息命中率 | 78% | ≥75% | ✅ |
| 模板化率 | 12% | ≤20% | ✅ |
| 安全类case | 100% | =100% | ✅ |

## 辅助指标

| 指标 | 值 |
|------|------|
| 输出可用率(Judge) | 74% |
| 幻觉率 | 6% |
| 延迟P95 | 4.2s |
```

### 退出码

- 0 = PASS
- 1 = 门禁FAIL
- 2 = infra错误（超时/网络/API）

---

## 七、Badcase 去重 + 入库规则

### 去重键

```
source_case_id + dataset_version + model + category
```

source_case_id = testset中的case.id（不是自动生成的）
不使用自动生成的case_id做去重

### 入库条件

- error_type = model_failure → 入库
- error_type = schema_failure → 入库
- error_type = infra_failure → 不入库，单独记录到 manifest.json

### 修复条件

- 连续3次回归通过 → 可标fixed（需人工确认或自动）
- fixed=true 的case不再参加常规回归（除非--all）

---

## 八、执行顺序

```
Step 0: 确认Hook就位 (.claude/settings.json)
  ↓
Step 1: 数据契约定义 + Runner产物契约
  Task A: 创建 standard_testset_v2.json (50条)
  Task B: 创建 run_eval.py (支持direct/api双模式 + 产物输出)
  Task C: 创建 scorer.py (脚本打分3项)
  → 可并行，但A和B需要共享数据契约格式
  ↓
Step 2: 立即跑基线 (不开启Judge)
  Task D: python3 scripts/evals/run_eval.py --mode direct --limit 5
  → 验证Runner能跑通
  ↓
Task E: python3 scripts/evals/run_eval.py --mode direct --full
  → 拿到baseline数字
  ↓
Step 3: Claude Code Judge + Badcase回归
  Task F: 创建 judge_eval.py (调claude -p做裁判)
  Task G: 修改run_eval.py集成--judge参数
  Task H: 修改badcase_manager.py去重逻辑
  → 可并行
  ↓
Step 4: 跑完整评测 (含Judge) + 对抗集
  Task I: python3 scripts/evals/run_eval.py --mode api --judge
  Task J: 创建 adversarial_testset_v1.json (30条)
  Task K: 创建 holdout_testset_v1.json (10条)
  → I单独跑，J和K可并行
  ↓
Step 5: 部署验证 + 报告
  Task L: Langfuse部署验证
  Task M: 更新PROJECT_REPORT.md (填入真实数字)
  Task N: 更新前端
  ↓
Step 6: git commit + WeChat通知
```

---

## 九、验收标准

### 冒烟验证（必须先过）

- [ ] `run_eval.py --mode direct --limit 3` 跑完不报错
- [ ] 产物目录有 manifest.json + case_results.jsonl + summary.json
- [ ] 后端 health check 返回 healthy
- [ ] 前端加载返回 HTTP 200

### 核心验收

- [ ] 任务完成率 ≥ 80%
- [ ] 关键信息命中率 ≥ 75%
- [ ] 模板化率 ≤ 20%
- [ ] 安全类case = 100%
- [ ] badcase回归通过率 = 100%
- [ ] PROJECT_REPORT.md 所有xx→xx被真实数据替换
- [ ] PE架构优化有实验式记录（变更/不变/baseline/current/delta）
- [ ] 模型选型优化有实验式记录

### 附加验收

- [ ] 对抗集30条有结果
- [ ] hold-out集10条有结果
- [ ] Langfuse有Agent调用trace
