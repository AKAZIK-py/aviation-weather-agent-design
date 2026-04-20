# 航空气象 Agent — 项目报告

> 更新日期: 2026-04-20
> 项目位置: /Users/twzl/aviation-weather-projects/aviation-weather-agent
> 项目版本: v6.0 (E2E Chat UI + 可观测性)

---

## 一、项目概述

基于大语言模型的航空气象报文（METAR）智能分析系统，面向四类角色（飞行员、签派员、预报员、地勤机务）提供个性化天气分析报告。系统采用"规则引擎确定性解析 + LLM 语义理解"混合架构，严格遵循 ICAO Annex 3 标准。

### 核心特性

- **ICAO 标准合规**: 严格遵循 ICAO Annex 3 标准进行 METAR 解析和飞行规则判定
- **多角色分析**: 飞行员、签派员、气象预报员、地勤四种专业视角
- **动态风险引擎**: 基于能见度、云底高、风况的动态风险权重评估
- **LangGraph 工作流**: 声明式多节点工作流编排
- **全链路可观测性**: Prometheus + Grafana + Langfuse 三级监控
- **E2E Chat UI**: 实时对话界面 + SSE 流式输出 + 自动评测

### 技术栈

| 组件 | 技术选型 |
|------|----------|
| Agent 引擎 | FastAPI + LangGraph + 百度 ERNIE-4.0 |
| LLM 客户端 | DeepSeek / ERNIE-4.0 (多 provider 降级) |
| METAR 解析 | 自研 ICAO-compliant 解析器 |
| 风险评估 | 动态权重引擎 + 规则引擎 |
| 前端 | Next.js 15 + Tailwind CSS + shadcn/ui |
| 评测 | 4+2 指标体系 + 三层评测集 |
| 可观测性 | Prometheus + Grafana + Langfuse + Live Metrics |
| 开发工具 | Claude Code + Codex + 三层 Hook |

---

## 二、项目规模

### 代码统计

| 子项目 | 语言 | 代码行数 | 说明 |
|--------|------|----------|------|
| aviation-weather-agent (核心) | Python | ~19,000 | FastAPI 后端 + LangGraph Agent |
| aviation-weather-frontend | TypeScript | ~8,000 | Next.js 15 前端 |
| aviation-weather-ai | Python | ~3,000 | 评测模块 |
| 测试 | Python | ~5,000 | 428+ 单元测试 |
| 脚本/监控 | Shell/YAML | ~2,000 | Hook + 评测 Runner + 监控配置 |
| **总计** | - | **~37,000** | - |

### 文件结构

```
aviation-weather-agent/
├── app/                           # 核心应用
│   ├── agent/                     # LangGraph ReAct 循环
│   │   ├── graph.py               # 工作流定义
│   │   └── prompts.py             # PE V3 约束边界
│   ├── api/                       # FastAPI 路由
│   │   ├── routes_v3.py           # SSE 流式接口
│   │   └── schemas.py             # 请求/响应模型
│   ├── core/                      # 核心引擎
│   │   ├── llm_client.py          # 多 provider LLM 客户端
│   │   ├── config.py              # 配置管理
│   │   └── workflow.py            # 工作流引擎
│   ├── nodes/                     # LangGraph 节点
│   ├── prompts/                   # PE 模板
│   ├── services/                  # 业务服务
│   │   ├── live_metrics.py        # 实时指标采集
│   │   ├── auto_evaluator.py      # 自动评测
│   │   ├── eval_store.py          # 评测结果存储
│   │   ├── memory.py              # SQLite FTS5 记忆
│   │   └── role_reporters/        # 4 角色输出策略
│   ├── tools/                     # Agent 工具
│   │   └── weather_tools.py       # METAR 解析/风险评估
│   ├── utils/                     # 工具函数
│   └── evaluation/                # 评测框架
├── aviation-weather-frontend/     # Next.js 前端
│   └── src/
│       ├── app/                   # 页面路由
│       ├── components/            # UI 组件
│       │   ├── chat/              # 聊天界面
│       │   ├── metrics/           # 指标仪表板
│       │   └── sidebar/           # 侧边栏
│       └── lib/                   # 工具库
├── eval/                          # 评测数据集
│   ├── datasets/                  # 三层评测集
│   │   ├── standard_testset_v2.json (50条)
│   │   ├── boundary_testset_v1.json (100条)
│   │   ├── adversarial_testset_v1.json (30条)
│   │   └── holdout_testset_v1.json (10条)
│   ├── badcases/                  # 失败样本
│   └── results/                   # 评测结果
├── scripts/                       # 脚本工具
│   ├── evals/                     # 评测 Runner
│   └── hooks/                     # 三层 Hook
├── monitoring/                    # 监控配置
│   ├── prometheus/                # Prometheus 配置
│   ├── grafana/                   # Grafana 仪表板
│   └── alertmanager/              # 告警配置
├── tests/                         # 测试套件
├── config/                        # 配置文件
├── CLAUDE.md                      # 项目规范
├── EVOLUTION_PLAN.md              # 进化方案
├── EXECUTION_PLAN.md              # 执行计划
└── PROJECT_REPORT.md              # 本文件
```

---

## 三、核心指标 (4+2 体系)

### 主指标 (Agent 价值)

| 指标 | 基线 | 当前 | 目标 | 状态 |
|------|------|------|------|------|
| 任务完成率 | 60% | 98% | ≥80% | ✅ 超目标 18pp |
| 关键信息命中率 | 7% | 68% | ≥75% | ⚠️ 差 7pp |
| 输出可用率 | 40% | 98% | ≥70% | ✅ 超目标 28pp |
| Badcase 回归通过率 | N/A | 100% | ≥95% | ✅ 首次建立即达标 |

### 辅助指标 (护栏)

| 指标 | 基线 | 当前 | 目标 | 状态 |
|------|------|------|------|------|
| 幻觉率 | 80% | <5% | ≤10% | ✅ 大幅改善 |
| P95 延迟 | 33s | 21.3s | ≤15s | ⚠️ 仍超 6.3s |

### 全量评测结果

```
标准集 (50条): 通过率 98% (49/50), avg_score 0.68, P95 21335ms, Gate PASS
对抗集 (30条): 通过率 100% (30/30), avg_score 0.55, P95 20196ms, Gate PASS
Hold-out (10条): 通过率 100% (10/10), avg_score 0.79, P95 22845ms, Gate PASS
```

---

## 四、已修复问题

| Case | 问题 | 严重度 | 根因 | 修复 |
|------|------|--------|------|------|
| STD_001 | 9999 描述为 "6-10km" 而非 ">10km" | 中 | format_visibility 阈值 | ✅ visibility.py |
| STD_003 | 风向 270° 推荐 02 跑道 | 高 | Agent 凭空猜跑道号 | ✅ prompts.py 约束 |
| STD_004 | 获取实时 METAR 替代提供数据 | **严重** | Agent 未使用 metar_raw | ✅ prompts.py |
| STD_005 | get_approach_minima 工具报错 | 中 | 参数传错 | ✅ weather_tools.py |
| 通用 | 模板化输出 (60%) | 高 | markdown 标题+套话 | ✅ PE 收紧 |
| E2E | Radix TabsContent flex 高度不传播 | 中 | CSS 布局缺陷 | ✅ 手动条件渲染 |
| E2E | 后端根路径返回原始 JSON | 低 | 缺少仪表板 | ✅ HTML Dashboard |
| 基础 | httpx 代理 502 | 高 | 走代理访问 localhost | ✅ trust_env=False |

---

## 五、E2E Chat UI (2026-04-19 新增)

### 功能

- **实时对话界面**: 角色选择 + 消息输入 + SSE 流式输出
- **自动评测**: 每次对话自动触发 4+2 指标评测
- **评测结果存储**: eval_store 持久化，支持历史查询
- **Badcase 沉淀**: 评测失败自动沉淀为 badcase
- **指标仪表板**: KPI 卡片 + 趋势图 + Badcase 列表
- **Live Metrics**: 后端实时 token/延迟/provider 监控

### 技术实现

| 组件 | 实现 | 文件 |
|------|------|------|
| SSE 流式 | FastAPI EventSourceResponse | app/api/routes_v3.py |
| 自动评测 | 每次对话后触发 scorer | app/services/auto_evaluator.py |
| 评测存储 | JSONL 文件 + 内存缓存 | app/services/eval_store.py |
| Live Metrics | 单例聚合器 | app/services/live_metrics.py |
| HTML Dashboard | 根路径返回实时仪表板 | app/main.py |
| 前端 Chat | React + Tailwind + SSE | src/app/page.tsx |
| 前端 Metrics | KPI 卡片 + 趋势图 | src/components/metrics/ |

---

## 六、可观测性栈

| 组件 | 端口 | 用途 |
|------|------|------|
| FastAPI | 8000 | 后端 API + HTML Dashboard |
| Next.js | 3000 | 前端 Chat UI |
| Langfuse | 3002 | LLM Trace 追踪 |
| Grafana | 3001 | Prometheus 指标可视化 |
| Prometheus | 9090 | 指标采集 |
| AlertManager | 9093 | 告警管理 |

### 监控指标

- **Agent 层**: 任务完成率、关键信息命中率、输出可用率、幻觉率
- **基础设施**: 请求延迟 P50/P95/P99、Token 用量、Provider 切换次数
- **业务层**: 各角色查询分布、机场热度、飞行规则分布

---

## 七、开发工作流 (三层 Hook)

### 第一层：安全网

| 组件 | 功能 | 状态 |
|------|------|------|
| block_dangerous.sh | 拦截 rm -rf / force push | ✅ |
| protect_sensitive.sh | 锁住 .env / credentials | ✅ |
| ruff format | 自动格式化 | ✅ |

### 第二层：改后即测

| 组件 | 功能 | 状态 |
|------|------|------|
| auto_test.sh | 关联测试失败阻断 | ✅ |
| .pre-commit-config.yaml | ruff + mypy | ✅ |
| pr-gate.yml | PR 强制测试通过 | ✅ |

### 第三层：规范+日志

| 组件 | 功能 | 状态 |
|------|------|------|
| log_operation.sh | 操作日志 | ✅ |
| auto_commit.sh | LLM commit message | ✅ |
| pre-push hook | L1 标准集 + L2 badcase 回归 | ✅ |

---

## 八、评测体系

### 4+2 指标

**主指标 (Agent 价值)**:
1. **任务完成率**: 脚本检测 — 输出是否包含结论
2. **关键信息命中率**: 逐条检查 expected_key_info
3. **输出可用率**: LLM-as-Judge 3 个二值问题
4. **Badcase 回归通过率**: 历史失败样本重跑

**辅助指标 (护栏)**:
5. **幻觉率**: LLM-as-Judge
6. **延迟/成本**: P95 + Token 用量

### 三层评测集

| 层级 | 数量 | 用途 | 更新频率 |
|------|------|------|----------|
| L1 标准集 | 50 条 | Git tag 锁，回归基线 | 每个 major 版本 |
| L2 边界集 | 100 条 | 边界条件测试 | 每月 |
| L3 对抗集 | 30 条 | 压力测试 | 每季度 |
| Hold-out | 10 条 | 过拟合检测 | 不更新 |

### Badcase 流程

```
检测 → 分类 → 入回归池 → 下次回归验证 → 通过则移除
```

---

## 九、PE 设计原则

### V3 约束边界模式

- **只定义**: "你是谁" + "你关注什么" + "你别碰什么"
- **不写死**: 思维链路步骤，输出格式
- **角色影响**: 关注点，不影响输出格式
- **温度配置**: 解析 0.0 / 决策 0.0 / 分类 0.3 / 生成 0.7 / Judge 0.0

### 输出约束

- 答案优先，结论先行
- 角色相关，不输出无关内容
- 无固定模板，无 markdown 标题，无套话
- 简单问题 3-5 句话直接给结论

---

## 十、启动指南

### 环境准备

```bash
cd aviation-weather-agent
cp .env.example .env
# 编辑 .env 填入 API Key
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 启动服务

```bash
# 后端 (端口 8000)
cd aviation-weather-agent
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 前端 (端口 3000)
cd aviation-weather-frontend
npm install
npm run dev
```

### 运行测试

```bash
cd aviation-weather-agent
source venv/bin/activate
python -m pytest tests/ -q

# 全量评测
python scripts/evals/run_eval.py --mode api --dataset standard
```

### 监控栈

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## 十一、已知限制

1. **延迟**: P95 21.3s，目标 ≤15s，LLM 调用是瓶颈
2. **关键信息命中率**: 68%，目标 ≥75%，语义匹配需进一步优化
3. **脏数据**: Badcase 列表中存在测试数据 BC_20260419_002
4. **Provider 稳定性**: 部分 Provider 偶发超时，需完善降级策略

---

## 十二、后续规划

1. **延迟优化**: 引入缓存 + 异步并行 + 模型量化
2. **命中率提升**: 优化语义匹配算法 + 扩充 golden set
3. **多语言支持**: 英文 METAR 解析 + 英文报告生成
4. **移动端适配**: 响应式设计 + PWA
5. **A/B 测试**: 多 PE 版本对比评测

---

## 附录

- 项目规范: `CLAUDE.md`
- 进化方案: `EVOLUTION_PLAN.md`
- 执行计划: `EXECUTION_PLAN.md`
- Hook 配置: `.claude/settings.json`
- 工具配置: `ruff.toml`
- 监控配置: `monitoring/`
- 评测数据: `eval/datasets/`
- Badcase: `eval/badcases/`
- 评测结果: `eval/results/`
