# 航空气象 Agent — 最终交付报告

**文档编号**：AV-AGENT-FINAL-2026
**版本**：v5.0
**项目时间**：2026-04-01 ～ 2026-04-12
**项目负责人**：twzl
**技术栈**：FastAPI + LangGraph + 百度千帆 ERNIE-4.0 + Next.js 15
**遵循标准**：ICAO Annex 3 + 动态权重系统

---

# 一、项目背景

## 1.1 项目概述

基于大语言模型的航空气象报文（METAR）智能分析系统，面向四类角色（飞行员、签派员、预报员、地勤机务）提供个性化天气分析报告。系统采用"规则引擎确定性解析 + LLM 语义理解"混合架构。

## 1.2 核心特性

- METAR 自动解析（ICAO 标准，支持 VV/WS/RVR/负温度/CAVOK/NSC/BECMG-TEMPO）
- **4 角色独立节点** — 每个角色独立的 system prompt、输出 Schema、风险因素过滤、建议生成
- **动态风险引擎** — 云底高/能见度 5 级区间 + 28 种天气现象权重矩阵 + 强制覆盖规则
- 15 维安全边界检测 + 积冰/颠簸/跑道污染/VV 极端值/气压异常
- 多层级 LLM 降级（4 层）+ Circuit Breaker + 三级缓存
- 全链路可观测性（Prometheus + NodeTracer）
- 角色驱动的渐进式前端（固定头部 → 角色摘要 → 主区域 → 折叠区 → 页脚）

## 1.3 系统能力边界

| 使用场景 | 系统角色 | 最终决策者 |
|---------|---------|-----------|
| METAR 解析 | AI 独立完成 | 无需人工 |
| 飞行规则初判 | AI 辅助 | 签派员/飞行员复核 |
| 风险等级评估 | AI 辅助 | 持证气象人员确认 |
| 进近 DH/MDA | AI 仅参考 | 飞行员自行决断 |
| 签派放行 | AI 禁止决策 | 签派员法定决策 |
| 紧急情况 | AI 不参与 | 机组/管制员 |

## 1.4 技术架构

```
航空气象 Agent v5.0
├── Layer 1: METAR 解析层
│   ├── ICAO 标准正则 (16种天气代码)
│   ├── VV/WS/RVR/负温度/CAVOK/NSC/AO1-AO2/BECMG-TEMPO
│   └── 双轨飞行规则 (icao/golden_set)
├── Layer 2: 区间诊断层
│   ├── 云底高 6 级区间 (Zone 1-6, ±100-200ft 缓冲)
│   ├── 能见度 5 级区间 (对数归一化 0-100)
│   └── 温度积冰 6 档连续映射
├── Layer 3: 动态权重层
│   ├── 28 种天气现象权重矩阵 (归一化 sum=1.0)
│   ├── 多现象叠加: 取各维度权重最大值
│   └── 大风三维评估 (瞬时/阵风差值/侧风) + W-01~04
├── Layer 4: 综合评分层
│   ├── 加权评分 + 强制覆盖 (FZRA三重验证/WS/SS)
│   └── 双轨飞行规则映射
├── Layer 5: 4 角色独立报告层 (新增)
│   ├── PilotReporter → ILS进近/备降/除冰/复飞
│   ├── DispatcherReporter → 放行状态/延误/备降方案
│   ├── ForecasterReporter → 趋势/SIGMET/危险天气
│   └── GroundCrewReporter → 户外作业/设备/除冰液/车辆
├── LLM 层
│   ├── 4 层降级 + Circuit Breaker
│   └── 每角色独立 system prompt (含职责+禁止输出)
├── 基础设施
│   ├── 三级缓存 (L1/L2/L3)
│   ├── Prometheus + NodeTracer
│   └── YAML 外置配置
└── 应用层
    ├── FastAPI V1/V2 (10 端点)
    ├── Next.js 15 前端 (10 场景 + 渐进式报告)
    └── 用户反馈闭环
```

---

# 二、项目规模

| 子项目 | Python | TypeScript | 代码行数 |
|--------|--------|-----------|---------|
| aviation-weather-agent | 86 files | - | 22,035 |
| aviation-weather-frontend | - | 27 files | 3,651 |
| aviation-weather-ai | 14 files | - | 5,586 |
| **合计** | **100 files** | **27 files** | **31,272** |

**测试用例**：428 个测试函数

---

# 三、核心模块清单

## 3.1 角色独立报告架构（本轮新增）

| 文件 | 职责 |
|------|------|
| `role_reporters/base.py` | BaseReporter — 风险因素角色过滤 + 模板方法 |
| `role_reporters/pilot.py` | 飞行员：ILS进近/备降/除冰/复飞/决断高 |
| `role_reporters/dispatcher.py` | 签派：放行状态/延误概率/备降方案/燃油策略 |
| `role_reporters/forecaster.py` | 预报员：天气趋势/SIGMET建议/危险天气评估 |
| `role_reporters/ground_crew.py` | 地勤：户外作业/设备限制/除防冰/航材存储 |

**角色隔离验证**（同一份冻雾 METAR）：

| 内容 | 飞行员 | 签派 | 预报员 | 地勤 |
|------|--------|------|--------|------|
| ILS 进近标准 | ✅ | ❌ | ❌ | ❌ |
| 备降建议 | ✅ | ✅ | ❌ | ❌ |
| 天气趋势分析 | ❌ | ❌ | ✅ | ❌ |
| 户外作业状态 | ❌ | ❌ | ❌ | ✅ |
| 除冰液储备 | ❌ | ❌ | ❌ | ✅ |
| **交叉污染** | **零** | **零** | **零** | **零** |

## 3.2 动态风险引擎

| 模块 | 文件 | 职责 |
|------|------|------|
| 云底高区间 | `ceiling_zones.py` | 6 级区间 + 缓冲区 |
| 能见度区间 | `visibility_zones.py` | 5 级区间 + 对数归一化 |
| 动态权重 | `dynamic_weights.py` | 28 种天气现象权重矩阵 |
| 大风评估 | `wind_assessment.py` | 三维评估 + W-01~04 |
| 综合引擎 | `dynamic_risk_engine.py` | 加权评分 + 强制覆盖 |

## 3.3 基础设施

| 模块 | 职责 |
|------|------|
| `circuit_breaker.py` | CLOSED/OPEN/HALF_OPEN 三态熔断 |
| `llm_client.py` | 4 层降级 + ResilientLLMClient |
| `cache.py` | L1/L2/L3 三级缓存 |
| `observability.py` | Prometheus + NodeTracer |
| `config.py` + `agent_config.yaml` | YAML + 环境变量 |

## 3.4 评测模块

| 模块 | 职责 |
|------|------|
| `d1_evaluator.py` | D1 子维度评测 (D1.1-D1.6) |
| `d1_root_cause.py` | D1 根因分析 (5 类根因) |
| `hallucination_detector.py` | 三层幻觉检测 |
| `reliability_audit.py` | D2/D4 可靠性审查 |
| `test_evaluation_suite.py` | 101 个评测用例 |

---

# 四、前端架构

## 4.1 渐进式报告布局

```
┌─────────────────────────────────────┐
│ [固定头部] ZSPD · 飞行员 · CRIT · LIFR │
├─────────────────────────────────────┤
│ ⛔ NO-GO — 3 个关键原因               │  ← 角色摘要
│   • 能见度 <1km                      │
│   • 云底 300ft 仅 ILS III 可行        │
│   • 积冰条件成立                      │
├─────────────────────────────────────┤
│ 【决断高与进近】                      │  ← 角色主区域
│ ILS I ✅ | ILS II ✅ | ILS III ✅     │  (按角色过滤)
│ VOR ❌ | NDB ❌ | 目视 ❌             │
├─────────────────────────────────────┤
│ ── ▼ 展开补充信息 ──                  │  ← 折叠区
│ ── ▼ 展开原始数据 ──                  │  ← 折叠区
├─────────────────────────────────────┤
│ 能力边界 · ICAO Annex 3 · v5.0       │  ← 页脚
└─────────────────────────────────────┘
```

## 4.2 天气模拟场景（10 个）

| 场景 | 风险 |
|------|------|
| ☀️ 正常天气 | LOW |
| 🥶 寒潮降温 | HIGH |
| 🌫️ 低能见度 | MEDIUM |
| ⛈️ 雷暴大风 | CRITICAL |
| ❄️ 冻雾结冰 | HIGH |
| 🌨️ 大雪天气 | HIGH |
| 💨 强侧风 | MEDIUM |
| 🌀 台风外围 | CRITICAL |
| 🌪️ 沙尘暴 | CRITICAL |
| 🧊 冻雨积冰 | CRITICAL |

## 4.3 动态指标

- 实时累计：总请求 / 成功率 / 平均延迟
- 最新分析：飞行规则 / 风险等级 / LLM 调用 / 处理耗时
- 每次分析后自动更新

---

# 五、ICAO 标准

| 类别 | 能见度 | Ceiling |
|------|--------|---------|
| VFR | ≥ 5 SM (≥ 8000m) | ≥ 3,000 ft |
| MVFR | 3-5 SM (4800-8000m) | 1,000-3,000 ft |
| IFR | 1-3 SM (1600-4800m) | 500-1,000 ft |
| LIFR | < 1 SM (< 1600m) | < 500 ft |

Ceiling = 最低 BKN/OVC/VV 高度。FEW/SCT 不算。适飞标准：< 1km = CRITICAL。

---

# 六、关键设计决策

| 决策 | 传统 | 本方案 | 理由 |
|------|------|--------|------|
| 报告生成 | 1 个通用 LLM 节点 | 4 个角色独立 reporter | 消除上下文污染 |
| 云底高 | 硬阈值 | 6 级区间 + 缓冲区 | 消除边界反转 |
| 能见度 | 硬阈值 | 5 级区间 + 对数映射 | 更符合感知 |
| 风险分数 | 无上限 | min(..., 100) cap | 防止爆表 |
| 权重 | 不归一化 | sum=1.0 归一化 | 数学正确 |
| FZRA 覆盖 | 无条件 95 分 | 三重验证 (T≤0 + VIS<5 + DPD<3) | 避免误判 |
| 声明 | 报告文本内 | 独立字段 + 页脚 | 不污染 LLM 输出 |
| 建议 | 通用模板 | 按角色 + 按风险因素 | 有针对性 |

---

# 七、API 接口

## V1 (`/api/v1`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/analyze` | POST | METAR 分析 |
| `/health` | GET | 健康检查 |
| `/airports` | GET | 机场列表 |
| `/metrics` | GET | Prometheus 指标 |
| `/feedback` | POST | 提交反馈 |
| `/feedback/stats` | GET | 反馈统计 |

## V2 (`/api/v2`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/analyze` | POST | 增强分析（含 role_report + role_summary + disclaimer） |
| `/airports/{icao}/metar` | GET | 机场 METAR |
| `/airports/{icao}/report/{role}` | GET | 角色报告 |

---

# 八、配置管理

`config/agent_config.yaml`:
- agent.version: 2.1.0
- llm.primary: qianfan/ernie-4.0
- llm.fallback_tiers: ernie-speed → deepseek → rule-engine
- cache.ttl: 1800s (METAR) / 3600s (role)
- flight_rules.standard: icao
- risk_thresholds: vis critical=1.0km, high=3.0km

---

# 九、总结

## 9.1 项目亮点

1. **4 角色独立架构** — 零交叉污染，每个角色只看到相关内容
2. **动态风险引擎** — 区间诊断 + 权重矩阵 + 强制覆盖，解决硬阈值反转
3. **渐进式前端** — 固定头部 → 角色摘要 → 主区域 → 折叠 → 页脚
4. **生产级稳定** — 4 层 LLM 降级 + Circuit Breaker + 三级缓存
5. **428 个测试** — 解析/风险/缓存/边界/动态引擎/评测套件
6. **ICAO 合规** — 飞行规则严格遵循 Annex 3，双轨评测

## 9.2 后续建议

1. 配置百度千帆 API Key 恢复 LLM 分析
2. Docker 容器化 + K8s 部署
3. 基于用户反馈迭代权重矩阵
4. 接入真实 METAR 数据源（aviationweather.gov）

---

*报告版本：v5.0（最终版）*
*生成日期：2026-04-12*
*项目代码：31,272 行 / 测试：428 用例*
*遵循标准：ICAO Annex 3*
