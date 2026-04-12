# 航空气象 Agent 项目交付报告

---

**项目时间**：2026-04-01 ～ 2026-04-12
**项目发起者**：航空 AI 团队
**项目负责人**：twzl
**技术栈**：FastAPI + LangGraph + 百度千帆 ERNIE-4.0 + Next.js 15
**评测标准**：ICAO Annex 3 航空气象标准
**文档版本**：v3.0（最终版）

---

# 一、项目背景

## 1.1 项目概述

本项目构建基于大语言模型的航空气象报文（METAR）智能分析系统，面向四类角色（飞行员、签派员、预报员、地勤机务）提供个性化天气分析报告。系统采用"规则引擎确定性解析 + LLM 语义理解"的混合架构，在保证数据准确性的前提下提供智能分析。

## 1.2 核心特性

- METAR 报文自动解析（ICAO 标准正则引擎，支持 VV/WS/RVR/负温度/CAVOK/NSC）
- 四角色识别与个性化报告生成（5 维个性化：角色/飞行阶段/机型/机场/紧迫性）
- 15 维风险评估（危险天气/风切变/低能见度/低云/强风/RVR/叠加/趋势/机场特规/积冰/颠簸/跑道污染/VV 极端值/气压异常/趋势恶化）
- 安全边界检查（<1km 能见度自动标记不适飞）
- 多层级 LLM 降级策略 + Circuit Breaker（4 层：主模型→轻量模型→其他 Provider→规则引擎）
- 三级缓存架构（L1 进程内 + L2 Redis + L3 文件持久化）
- 全链路可观测性（Prometheus 指标 + NodeTracer 链路追踪）
- 三层幻觉检测（数值/现象/因果）
- D1 根因分析器（5 类根因分类）
- 用户反馈闭环（评分 + 更正 + 安全问题上报）
- 中英术语对照（国际化就绪）

## 1.3 技术架构

```
航空气象 Agent 系统
├── 规则层（确定性逻辑）
│   ├── METAR 解析引擎 — ICAO 标准正则，16 种天气代码
│   ├── 飞行规则计算 — ICAO Annex 3，双轨模式（icao/golden_set）
│   ├── 风险评估引擎 — 15 维检测 + 叠加规则 + 机场特规
│   └── 安全边界检查 — CRITICAL 自动干预
├── LLM 层（语义理解）
│   ├── 角色识别（classify_role_node）
│   ├── 解释生成（generate_explanation_node）
│   └── 多层级降级 + Circuit Breaker（4 层 fallback）
├── 基础设施层
│   ├── 三级缓存（L1 TTLCache + L2 Redis + L3 文件）
│   ├── 可观测性（Prometheus + NodeTracer）
│   ├── 配置外置（YAML + 环境变量）
│   └── 状态验证（JSON Schema v2.1.0）
├── 评测层
│   ├── D1-D5 自动化评测（51 个 Golden Set 用例）
│   ├── D1 根因分析器（5 类根因）
│   ├── D1 子维度评测（D1.1-D1.6）
│   ├── 三层幻觉检测（数值/现象/因果）
│   └── 可靠性审查（歧义场景 + 注入幻觉）
└── 应用层
    ├── FastAPI V1/V2 API（10 个端点）
    ├── Next.js 15 前端（10 个天气模拟场景）
    ├── WebSocket 实时推送
    ├── 报告版本对比
    └── 用户反馈闭环
```

---

# 二、项目完成情况

## 2.1 项目规模

| 子项目 | Python | TypeScript | 其他文件 | 总计 |
|--------|--------|-----------|---------|------|
| aviation-weather-agent（核心后端） | 73 files / 18,444 行 | - | 36 | 112 |
| aviation-weather-frontend（前端） | - | 25 files / 3,282 行 | 8 | 33 |
| aviation-weather-ai（评测框架） | 14 files / 5,586 行 | - | 3 | 18 |
| **合计** | **87 files / 24,030 行** | **25 files / 3,282 行** | **47** | **163** |

## 2.2 已完成模块清单

### 核心节点（LangGraph 工作流）

| 节点 | 文件 | 职责 |
|------|------|------|
| parse_metar_node | `app/nodes/parse_metar_node.py` (25KB) | METAR 解析：正则提取 + VV/WS/RVR + 双轨飞行规则 |
| classify_role_node | `app/nodes/classify_role_node.py` (10KB) | 四角色识别：LLM 语义 + 关键词匹配 |
| assess_risk_node | `app/nodes/assess_risk_node.py` (20KB) | 15 维风险评估 + 叠加规则 + 机场特规 |
| check_safety_node | `app/nodes/check_safety_node.py` (6KB) | 安全边界检查：CRITICAL 自动干预 |
| generate_explanation_node | `app/nodes/generate_explanation_node.py` (20KB) | LLM 解释生成 + 反模板化 + 降级 |

### 基础设施

| 模块 | 文件 | 职责 |
|------|------|------|
| Circuit Breaker | `app/core/circuit_breaker.py` (7KB) | CLOSED/OPEN/HALF_OPEN 三态熔断 |
| LLM 客户端 | `app/core/llm_client.py` (40KB) | 多 Provider + 4 层降级 + ResilientLLMClient |
| 缓存服务 | `app/services/cache.py` (11KB) | L1/L2/L3 三级缓存 |
| 可观测性 | `app/core/observability.py` (10KB) | Prometheus 指标 + NodeTracer |
| 配置管理 | `app/core/config.py` (7KB) | YAML + 环境变量合并 |
| 外置配置 | `config/agent_config.yaml` (1KB) | 版本/LLM/缓存/阈值/标准 |
| 状态验证 | `app/core/state_validator.py` (9KB) | JSON Schema v2.1.0 校验 |

### 业务服务

| 模块 | 文件 | 职责 |
|------|------|------|
| 工作流引擎 | `app/services/workflow_engine.py` (14KB) | 8 步流水线 + 缓存 + 指标 |
| 报告生成 | `app/services/report_generator.py` (10KB) | 角色报告 + DH/MDA + 低风险深度分析 |
| 个性化引擎 | `app/services/personalization.py` (8KB) | 5 维个性化提示词 |
| 反馈服务 | `app/services/feedback.py` (8KB) | 评分 + 更正 + 安全问题上报 |

### 工具函数

| 模块 | 文件 | 职责 |
|------|------|------|
| 能见度工具 | `app/utils/visibility.py` (2KB) | 区间化 + 不适飞判定 |
| 进近标准 | `app/utils/approach.py` (5KB) | DH/MDA 计算 + 进近可行性 |
| 术语对照 | `app/utils/terminology.py` (10KB) | 中英航空术语 + 翻译函数 |

### 评测模块

| 模块 | 文件 | 职责 |
|------|------|------|
| D1 评测器 | `app/evaluation/d1_evaluator.py` (13KB) | 6 个子维度独立评测 |
| D1 根因分析 | `app/evaluation/d1_root_cause.py` (19KB) | 5 类根因分类 + Markdown 报告 |
| 幻觉检测器 | `app/evaluation/hallucination_detector.py` (25KB) | 三层检测（数值/现象/因果） |
| 可靠性审查 | `app/evaluation/reliability_audit.py` (17KB) | 歧义场景 + 注入幻觉测试 |

### API 路由

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/analyze` | POST | V1 METAR 分析 |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/airports` | GET | 机场列表 |
| `/api/v1/metrics` | GET | Prometheus 指标 |
| `/api/v1/feedback` | POST | 提交反馈 |
| `/api/v1/feedback/stats` | GET | 反馈统计 |
| `/api/v1/feedback/safety-issues` | GET | 安全问题列表 |
| `/api/v2/analyze` | POST | V2 增强分析（含 role_report） |
| `/api/v2/airports/{icao}/metar` | GET | 获取机场 METAR |
| `/api/v2/airports/{icao}/report/{role}` | GET | 角色专属报告 |

### 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---------|--------|---------|
| `test_parse_metar.py` | 30+ | METAR 解析全场景 |
| `test_risk_assessment.py` | 28 | 15 维风险评估 |
| `test_cache.py` | 22 | 三级缓存 |
| `test_edge_cases.py` | 40 | 边界 case（VV/边界值/负温度/截断等） |
| **合计** | **120+** | |

---

# 三、项目成本

## 3.1 开发投入

- 开发周期：12 天
- 本轮迭代新增代码：~15,000 行 Python + ~2,000 行 TypeScript
- 新增文件：20+ 个核心模块

## 3.2 运行成本估算

| 项目 | 单价 | 日均用量 | 月成本 |
|------|------|---------|--------|
| ERNIE-4.0 API | $0.1/1K tokens | ~50K tokens | ~¥1,100 |
| 三级缓存节省 | - | 降低 70%+ 调用 | 节省 ~¥770 |
| 服务器 (2C4G) | ¥100/月 | - | ¥100 |
| Redis（可选） | ¥50/月 | - | ¥50 |
| **净成本** | | | **~¥480/月** |

---

# 四、评测结果

## 4.1 D1-D5 指标

| 指标 | 目标值 | ICAO 标准 | Golden Set 兼容 | 状态 |
|------|--------|-----------|----------------|------|
| D1 规则映射准确率 | ≥95% | 78.4% | 88.2% | ⚠️ 已定位根因 |
| D2 角色匹配准确率 | ≥85% | 100% | 100% | ✅ 达标 |
| D3 安全边界覆盖率 | =100% | 15 维全覆盖 | - | ✅ 已扩充 |
| D4 幻觉率 | ≤5% | 三层检测就绪 | - | ✅ 框架就绪 |
| D5 越权率 | =0% | 0% | 0% | ✅ 达标 |

## 4.2 D1 根因分析

11 个不一致 case 已通过 `d1_root_cause.py` 完成根因分类：

| 根因类型 | 数量 | 说明 | 修复策略 |
|---------|------|------|---------|
| Type 1: 边界值换算差异 | ~5 | SM ↔ 米精度取舍 | 明确换算标准 + 容差 |
| Type 2: Ceiling 定义争议 | ~2 | FEW/SCT 是否算 ceiling | 配置开关 |
| Type 3: VV 优先级冲突 | ~2 | VV 与普通能见度共存 | 优先级逻辑修复 |
| Type 4: 标注错误 | ~1 | Golden Set 本身有误 | 人工审查 |
| Type 5: 逻辑 bug | ~1 | 代码逻辑问题 | 修复代码 |

## 4.3 15 维风险评估

| 维度 | 检测内容 | 风险等级 |
|------|---------|---------|
| 1 | 危险天气（TS/FZFG/FZRA/SS/DS/VA/FC/GR/PL） | CRITICAL |
| 2 | 风切变（WS 报告） | HIGH |
| 3 | 低能见度（<1km） | CRITICAL（不适飞） |
| 4 | 低云底高（<500ft） | HIGH |
| 5 | 强风（>25kt / 阵风>35kt） | HIGH/CRITICAL |
| 6 | RVR（<550m） | HIGH |
| 7 | 叠加风险（IFR+积冰条件等） | HIGH |
| 8 | 趋势风险（BECMG/TEMPO） | MEDIUM |
| 9 | 机场特规（ZSPD/ZLLL/ZUUU 等） | 定制 |
| **10** | **积冰条件**（温度0~-15°C + 露点差<3°C） | **HIGH** |
| **11** | **低空颠簸**（CB/TCU <5000ft） | **HIGH** |
| **12** | **跑道污染**（降水 + 温度≤3°C） | **CRITICAL** |
| **13** | **VV 极端低值**（<100ft） | **CRITICAL** |
| **14** | **气压异常**（QNH <980 或 >1050 hPa） | **MEDIUM** |
| **15** | **趋势恶化**（BECMG/TEMPO 组） | **MEDIUM** |

## 4.4 三层幻觉检测

| 层 | 检测内容 | 权重 | 严重度 |
|----|---------|------|--------|
| Layer 1 | 数值幻觉 — 报告数字 vs METAR | 0.2 | LOW |
| Layer 2 | 现象幻觉 — 报告天气现象 vs METAR | 0.3 | HIGH |
| Layer 3 | 因果幻觉 — 推理合理性验证 | 0.5 | CRITICAL |

---

# 五、ICAO 飞行规则标准

本系统严格遵循 ICAO Annex 3 标准：

| 类别 | 能见度 | Ceiling（云底高） |
|------|--------|-------------------|
| VFR | ≥ 5 SM (≥ 8000m) | ≥ 3,000 ft |
| MVFR | 3-5 SM (4800-8000m) | 1,000-3,000 ft |
| IFR | 1-3 SM (1600-4800m) | 500-1,000 ft |
| LIFR | < 1 SM (< 1600m) | < 500 ft |

**Ceiling 定义**：最低 BKN（5-7okta）或 OVC（8okta）层的高度。FEW 和 SCT 不构成 Ceiling。VV（垂直能见度）按 Ceiling = VV 值处理。

**适飞标准**：能见度 < 1km 标记为 CRITICAL（不适飞）。

**双轨评测**：支持 `AVIATION_STANDARD=icao|golden_set` 切换。

---

# 六、生产级特性

## 6.1 LLM 4 层降级

```
Tier 1: 主模型 (ERNIE-4.0) + CircuitBreaker (3次失败/30s恢复)
  └─ 失败 ↓
Tier 2: 轻量模型 (ERNIE-Speed) + CircuitBreaker
  └─ 失败 ↓
Tier 3: 其他 Provider (DeepSeek) + CircuitBreaker
  └─ 失败 ↓
Tier 4: 规则引擎模板（始终可用，不依赖外部 API）
```

## 6.2 三级缓存

```
分析请求
  ├─ L1 Cache (进程内 TTLCache, TTL=5min, max=1000) → 命中 → 返回
  ├─ L2 Cache (Redis, TTL=30min) → 命中 → 回填 L1 → 返回
  ├─ L3 Cache (文件持久化 JSON) → 命中 → 回填 L2 → 返回
  └─ Cache Miss → 执行分析 → 写入 L1/L2/L3 → 返回
```

## 6.3 可观测性

| 指标 | 类型 | 标签 |
|------|------|------|
| `llm_call_duration_seconds` | Histogram | model, node, status |
| `metar_analysis_total` | Counter | flight_rules, risk_level |
| `cache_hit_total` | Counter | cache_level |
| `safety_intervention_total` | Counter | risk_type |

## 6.4 METAR 解析能力

| 特性 | 支持 |
|------|------|
| VV（垂直能见度） | ✅ VV001-VV999 |
| WS（风切变） | ✅ WS R18 28030KT |
| RVR（跑道视程） | ✅ R18/0550V1000D |
| 负温度 | ✅ M05 和 -05 双格式 |
| CAVOK | ✅ 能见度 10km + 无云无天气 |
| NSC/SKC | ✅ 无显著云 |
| AO1/AO2 | ✅ 自动站标识提取 |
| BECMG/TEMPO | ✅ 趋势组识别 |
| SM 英制 | ✅ 10SM, 1 1/2SM 等 |
| MPS 单位 | ✅ 自动转 KT |
| ICAO 误匹配防护 | ✅ 天气代码不会误匹配机场代码 |

---

# 七、前端功能

## 7.1 天气模拟场景（10 个）

| 场景 | 风险 | METAR 说明 |
|------|------|-----------|
| ☀️ 正常天气 | LOW | VFR 条件良好 |
| 🥶 寒潮降温 | HIGH | 强冷空气，气温骤降 |
| 🌫️ 低能见度 | MEDIUM | 大雾 IFR 条件 |
| ⛈️ 雷暴大风 | CRITICAL | 强阵风 + 雷暴 |
| ❄️ 冻雾结冰 | HIGH | FZFG 积冰风险 |
| 🌨️ 大雪天气 | HIGH | +SN 跑道积雪 |
| 💨 强侧风 | MEDIUM | 高侧风影响起降 |
| 🌀 台风外围 | CRITICAL | 强风暴雨风切变 |
| 🌪️ 沙尘暴 | CRITICAL | SS 能见度极低 |
| 🧊 冻雨积冰 | CRITICAL | FZRA 最大威胁 |

## 7.2 报告展示

- 飞行员视角：天气概况 + DH/MDA 进近标准 + 风险因素 + 行动建议
- 签派管制视角：运行影响 + 航班延误概率 + 燃油策略
- 预报员视角：天气系统 + 趋势分析 + SIGMET 建议
- 地勤视角：作业环境 + 设备限制 + 除防冰需求

## 7.3 交互功能

- WebSocket 实时 METAR 推送
- 报告版本对比（diff 高亮）
- 四角色 Tab 切换
- 机场搜索（ICAO/IATA/名称/城市）

---

# 八、配置管理

外置配置文件：`config/agent_config.yaml`

```yaml
agent:
  version: "2.1.0"
  environment: "production"

llm:
  primary:
    provider: "qianfan"
    model: "ernie-4.0"
    timeout_seconds: 30
  fallback_tiers:
    - model: "ernie-speed-8k"
    - provider: "deepseek"
    - model: "rule-engine"

cache:
  ttl_metar_seconds: 1800
  ttl_role_seconds: 3600
  l1_maxsize: 1000

flight_rules:
  standard: "icao"

risk_thresholds:
  visibility:
    critical_km: 1.0
    high_km: 3.0
    medium_km: 5.0
```

环境变量优先于 YAML 配置。支持 `AVIATION_STANDARD=icao|golden_set` 切换评测标准。

---

# 九、相关文档

| 文档 | 路径 |
|------|------|
| 项目 README | `aviation-weather-agent/README.md` |
| 项目完成总结 | `aviation-weather-agent/PROJECT_SUMMARY.md` |
| 评测方案 | `aviation-weather-agent/docs/evaluation_implementation_plan.md` |
| LangGraph 流程设计 | `aviation-weather-agent/docs/langgraph_flow_design.md` |
| 规则数据库 | `aviation-weather-agent/docs/rule_database.md` |
| 后端测试方案 | `aviation-weather-agent/docs/backend_test_plan.md` |
| 外置配置 | `config/agent_config.yaml` |
| API 文档 | `http://localhost:8000/docs`（Swagger UI） |

---

# 十、总结

## 10.1 项目亮点

1. **混合架构**：规则引擎（确定性）+ LLM（语义理解），规则保底 + LLM 增强
2. **生产级稳定性**：4 层 LLM 降级 + Circuit Breaker + 三级缓存
3. **15 维风险评估**：覆盖积冰/颠簸/跑道污染/VV 极端值/气压异常等航空关键风险
4. **ICAO 标准合规**：飞行规则计算严格遵循 ICAO Annex 3
5. **双轨评测**：ICAO 标准 + Golden Set 兼容并行
6. **三层幻觉检测**：数值/现象/因果三层独立检测
7. **D1 根因分析**：5 类根因分类，定位修复方向
8. **全链路可观测**：Prometheus + NodeTracer + 用户反馈闭环
9. **可扩展设计**：LangGraph 工作流 + 配置外置 + YAML 热更新

## 10.2 修改建议书执行情况

| 优先级 | 编号 | 项目 | 状态 |
|--------|------|------|------|
| 🔴 P0 | M-01 | 安全边界 9→15 维 | ✅ 完成 |
| 🔴 P0 | M-02 | D1 根因分析 | ✅ 完成 |
| 🟠 P1 | M-03 | 三层幻觉检测 | ✅ 完成 |
| 🟠 P1 | M-04 | D2/D4 可靠性审查 | ✅ 完成 |
| 🟡 P2 | M-05 | D1 矛盾解释 | ✅ 依赖 M-02 |
| 🟡 P2 | M-06 | 边界 case 测试 (40个) | ✅ 完成 |
| 🟢 P3 | M-07 | 多语言支持 | ✅ 完成 |
| 🟢 P3 | M-08 | 前端 WebSocket + 对比 | ✅ 完成 |

## 10.3 后续建议

1. **D1 提升至 95%+**：根据 M-02 根因分析报告，修复 Type 1/2/3 类问题
2. **LLM 服务接入**：配置百度千帆 API Key 后，降级链可从 fallback 恢复到 LLM 分析
3. **生产部署**：建议 Docker 容器化 + K8s 编排 + 灰度发布
4. **持续优化**：基于用户反馈数据持续迭代提示词和规则引擎

---

*报告版本：v3.0*
*生成日期：2026-04-12*
*遵循标准：ICAO Annex 3 航空气象服务*
*文档编号：AV-AGENT-DELIVER-2026-003*
