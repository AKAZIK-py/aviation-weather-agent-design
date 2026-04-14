# 航空气象Agent — 端到端进化方案

> 从"玩具demo"到生产级系统的完整改造方案
> 设计日期: 2026-04-14

---

## 总体架构（改造后）

```
                        ┌─────────────────────────────┐
                        │      Grafana Dashboard       │
                        │  (延迟/Token/失败率/幻觉率)   │
                        └──────────┬──────────────────┘
                                   │ 读取
                        ┌──────────▼──────────────────┐
                        │       Prometheus             │
                        │  (metrics: counters/gauges)  │
                        └──────────▲──────────────────┘
                                   │ scrape
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
   ┌─────▼──────┐          ┌──────▼───────┐          ┌──────▼───────┐
   │  Phoenix   │          │  Langfuse    │          │  自定义       │
   │ (幻觉评测)  │          │ (全链路追踪)  │          │  OTel SDK     │
   └─────▲──────┘          └──────▲───────┘          └──────▲───────┘
         │ OTel export             │ OTel native             │
         │                         │                         │
   ┌─────┴─────────────────────────┴─────────────────────────┴─────┐
   │                   OpenTelemetry Collector                      │
   │              (统一采集 → 分发到各后端)                          │
   └─────▲─────────────────────────────────────────────────────────┘
         │ 自动埋点
   ┌─────┴─────────────────────────────────────────────────────────┐
   │                    FastAPI + LangGraph Agent                   │
   │                                                                │
   │  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
   │  │ V3 API  │→ │ Agent    │→ │ 8 Tools   │→ │ Memory Layer │  │
   │  │ /chat   │  │ ReAct   │  │ (气象工具) │  │ (Mem0/自研)  │  │
   │  └─────────┘  └──────────┘  └───────────┘  └──────────────┘  │
   └───────────────────────────────────────────────────────────────┘
         │                           │
   ┌─────▼───────┐           ┌──────▼───────┐
   │  CI/CD Gate │           │  Eval Suite   │
   │ pre-push hook│───→──────│ (RAGAS+自定义)│
   │ 指标不达标   │  拒绝push │ Golden Set    │
   └─────────────┘           └──────────────┘
```

---

## 一、自动化评测流水线

### 1.1 评测工具选型

| 工具 | GitHub Stars | 定位 | 适用性 |
|------|-------------|------|--------|
| **RAGAS** | 13.4k | RAG评测框架 | ⚠️ 主要面向RAG，但支持自定义metric |
| **DeepEval** | 18k+ | LLM评测框架 | ✅ 14+内置指标，支持Agent评测，CI友好 |
| **Phoenix (Arize)** | 9.3k | 可观测+评测 | ✅ 自动trace评测，幻觉检测 |
| **Langfuse** | 24.9k | LLM工程平台 | ✅ 内置评测+数据集管理 |
| **Promptfoo** | 20k+ | Prompt评测 | ✅ CLI优先，CI/CD原生支持 |

**推荐组合：DeepEval + 自定义Golden Set**

理由：
- DeepEval有内置的`FaithfulnessMetric`(幻觉)、`ContextualRelevancyMetric`(上下文精度)、`ToolCorrectnessMetric`(工具调用准确率)
- 原生支持pytest集成，一条命令跑完全部评测
- 自带`deepeval test run` CLI，可直接嵌入git hook
- 比RAGAS更适合非RAG的Agent场景

### 1.2 评测指标体系

```
评测指标
├── D1: 规则映射准确率 (已有，≥95%)
├── D2: 角色匹配准确率 (已有，≥85%)
├── D3: 安全边界覆盖率 (已有，=100%)
├── D4: 幻觉率 (新增)
│   ├── Faithfulness: 输出是否忠于工具返回的数据
│   ├── Hallucination Score: 编造气象数据的比率
│   └── 阈值: ≤5%
├── D5: 越权率 (已有，=0%)
├── D6: 工具调用准确率 (新增)
│   ├── Tool Correctness: 是否选对了工具
│   ├── Tool Call Precision: 工具参数正确率
│   └── 阈值: ≥90%
├── D7: 上下文精度 (新增)
│   ├── Contextual Precision: 检索到的记忆是否相关
│   ├── Contextual Recall: 是否用到了该用的记忆
│   └── 阈值: ≥85% (记忆系统上线后)
└── D8: 端到端延迟 (已有)
    ├── P50 < 3s, P95 < 8s, P99 < 15s
```

### 1.3 CI/CD Gate 机制

```
开发者 git push
    ↓
pre-push hook 触发
    ↓
运行 deepeval test run tests/evaluation/
    ↓
    ├── 通过 → push 成功
    └── 失败 → push 被拒绝 + 输出失败详情
```

**实现方式:**
- `.git/hooks/pre-push` 脚本
- 或 GitHub Actions workflow (分支保护规则)
- 评测集驻留在 `evaluation/golden_set/` 目录
- 每次push自动跑51条Golden Set + 随机抽样20条边界case
- 全部通过才能push

### 1.4 关键开源工具

| 工具 | 用途 | 集成方式 |
|------|------|---------|
| **DeepEval** `pip install deepeval` | Agent评测框架 | pytest插件，CLI集成 |
| **deepeval test run** | 评测执行 | pre-push hook / GitHub Actions |
| **deepeval login** | 云端Dashboard查看历史(可选) | 本地+云端双模式 |

---

## 二、全链路可观测性

### 2.1 工具选型对比

| 维度 | **Langfuse** (24.9k⭐) | **Phoenix** (9.3k⭐) | **LangSmith** | **W&B Weave** |
|------|------------------------|---------------------|---------------|---------------|
| 开源 | ✅ 完全开源 | ✅ 完全开源 | ❌ 闭源SaaS | ⚠️ 部分开源 |
| 自部署 | ✅ Docker/K8s | ✅ pip一键启动 | ❌ | ⚠️ 有限 |
| OTel集成 | ✅ 原生支持 | ✅ 原生支持 | ⚠️ 需适配 | ⚠️ 需适配 |
| Prompt追踪 | ✅ 完整prompt+补全 | ✅ | ✅ | ✅ |
| Token统计 | ✅ input/output分开 | ✅ | ✅ | ✅ |
| 延迟追踪 | ✅ 端到端+每段 | ✅ | ✅ | ✅ |
| 成本追踪 | ✅ 按模型计价 | ✅ | ✅ | ✅ |
| 评测集成 | ✅ 内置scorer | ✅ 内置evaluator | ✅ | ✅ |
| LangGraph集成 | ✅ 一行代码 | ✅ 一行代码 | ✅ 原生 | ⚠️ |
| 幻觉检测 | ⚠️ 需配合 | ✅ 内置hallucination eval | ⚠️ | ⚠️ |
| 数据集管理 | ✅ | ✅ | ✅ | ✅ |
| 自托管难度 | 低(Docker Compose) | 极低(pip install) | N/A | 中 |

**推荐组合：Langfuse（全链路追踪）+ Phoenix（幻觉评测）+ Prometheus+Grafana（基础设施指标）**

### 2.2 指标分层

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: 业务指标 (Grafana Dashboard)                        │
│   幻觉率 / 决策准确率 / 用户满意度                           │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: AI质量指标 (Phoenix)                                │
│   Faithfulness / Hallucination Score / Eval Over Time       │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: LLM调用指标 (Langfuse)                              │
│   Prompt内容 / 补全内容 / Token消耗(I/O分开) / 模型延迟      │
│   Tool调用记录 / 每步ReAct迭代 / Trace完整链路               │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: 基础设施指标 (Prometheus)                            │
│   HTTP请求量/延迟/错误率 / 端到端延迟P50/P95/P99             │
│   活跃连接数 / 内存/CPU / LLM API失败率/重试次数             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Langfuse 追踪覆盖

Langfuse Python SDK 直接包装 LangChain/LangGraph，一行代码接入：

```python
from langfuse.callback import CallbackHandler
langfuse_handler = CallbackHandler()

# 在 create_reagent 中传入
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt,
)
# 运行时自动追踪
result = await agent.ainvoke(
    {"messages": messages},
    config={"callbacks": [langfuse_handler]}
)
```

自动捕获的字段：
- `input`: 完整的messages列表（含system prompt）
- `output`: 最终回答
- `usage.prompt_tokens` / `usage.completion_tokens`: Token消耗
- `latency`: 端到端延迟
- `model`: 使用的模型名
- `metadata`: session_id, user_id, role等
- 每步 tool_call 的 name, args, result

### 2.4 Prometheus 指标定义

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 请求指标
agent_requests_total = Counter(
    'agent_requests_total',
    'Total agent requests',
    ['role', 'provider', 'status']  # status: success/error/timeout
)

agent_request_duration_seconds = Histogram(
    'agent_request_duration_seconds',
    'Agent request duration',
    ['role', 'provider'],
    buckets=[0.5, 1, 2, 3, 5, 8, 13, 21, 34]  # 斐波那契分布
)

# LLM调用指标
llm_calls_total = Counter(
    'llm_calls_total',
    'Total LLM API calls',
    ['provider', 'model', 'status']
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['provider', 'model', 'direction']  # direction: input/output
)

llm_call_duration_seconds = Histogram(
    'llm_call_duration_seconds',
    'LLM API call latency',
    ['provider', 'model']
)

# 工具调用指标
tool_calls_total = Counter(
    'tool_calls_total',
    'Total tool calls',
    ['tool_name', 'status']  # status: success/error
)

tool_call_duration_seconds = Histogram(
    'tool_call_duration_seconds',
    'Tool call duration',
    ['tool_name']
)

# 质量指标
hallucination_score = Gauge(
    'hallucination_score',
    'Running hallucination score (0-1)',
    ['model']
)

eval_pass_rate = Gauge(
    'eval_pass_rate',
    'Golden set pass rate',
    ['eval_type']  # D1-D8
)
```

### 2.5 告警规则

```yaml
# prometheus/alerts.yml
groups:
  - name: aviation_agent_alerts
    rules:
      # LLM API失败率告警
      - alert: HighLLMErrorRate
        expr: rate(llm_calls_total{status="error"}[5m]) / rate(llm_calls_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "LLM API error rate > 10%"

      # 端到端延迟告警
      - alert: HighAgentLatency
        expr: histogram_quantile(0.95, rate(agent_request_duration_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Agent P95 latency > 10s"

      # 幻觉率告警
      - alert: HighHallucinationRate
        expr: hallucination_score > 0.1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Hallucination score > 10%"

      # 评测通过率下降
      - alert: EvalPassRateDropped
        expr: eval_pass_rate < 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Eval pass rate dropped below 85%"
```

### 2.6 关键开源工具清单

| 组件 | 工具 | 部署方式 | 用途 |
|------|------|---------|------|
| **LLM追踪** | Langfuse | `docker compose up` 自部署 | Trace/token/prompt/延迟 |
| **AI质量评测** | Phoenix | `pip install arize-phoenix` | 幻觉检测/质量趋势 |
| **指标采集** | OpenTelemetry SDK | `pip install opentelemetry-*` | 统一telemetry |
| **指标存储** | Prometheus | Docker | 时间序列指标 |
| **可视化** | Grafana | Docker | Dashboard |
| **告警** | Prometheus AlertManager | Docker | 阈值告警 |

---

## 三、记忆系统替代RAG

### 3.1 开源记忆方案对比

| 方案 | GitHub Stars | 记忆类型 | 语义检索 | 自动摘要 | 跨会话 | 部署复杂度 |
|------|-------------|---------|---------|---------|--------|-----------|
| **Mem0** | 22k+ | 用户/会话/实体 | ✅ 向量搜索 | ✅ | ✅ | 中(需向量DB) |
| **Letta (MemGPT)** | 13k+ | 核心/归档/回忆 | ✅ 分层检索 | ✅ 自动分页 | ✅ | 高(复杂架构) |
| **Zep** | 2k+ | 会话级 | ✅ | ✅ 自动摘要 | ⚠️ 有限 | 低 |
| **LangGraph Memory** | (LangChain生态) | 状态级 | ⚠️ 需自建 | ❌ | ⚠️ 需扩展 | 低 |
| **Hermes模式** | N/A | 文件系统 | ⚠️ 关键词搜索 | ❌ | ✅ | 极低 |

### 3.2 推荐方案：自研轻量记忆层（参考Hermes + Mem0思想）

不引入Mem0的全部重量级依赖（向量数据库等），而是借鉴其核心思想，结合Hermes的文件系统方案，构建三层记忆：

```
┌─────────────────────────────────────────────────────────┐
│                    记忆系统架构                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Layer 1: 会话记忆 (Session Memory)                     │
│  ├── 当前对话的完整消息历史                               │
│  ├── 存储: 内存 dict + 文件 JSON 持久化                  │
│  ├── 检索: 按时间序取最近N条                             │
│  └── 已实现 ✅                                          │
│                                                         │
│  Layer 2: 用户画像 (User Profile)                       │
│  ├── 跨会话偏好: preferred_role, home_base, aircraft    │
│  ├── 飞行习惯: 常用机场、关注时段、决策风格              │
│  ├── 存储: JSON文件                                     │
│  ├── 检索: 直接读取，注入system prompt                  │
│  └── 已实现(基础版) ✅，需扩展 ⚠️                       │
│                                                         │
│  Layer 3: 语义记忆 (Semantic Memory) — 待实现           │
│  ├── 历史分析结果的摘要和索引                            │
│  ├── 重要气象模式的积累                                  │
│  ├── 存储: SQLite + FTS5全文搜索                        │
│  ├── 检索: FTS5关键词 + embedding余弦相似度(可选)        │
│  └── 参考: Hermes的session_search                       │
│                                                         │
│  Layer 4: 自动摘要 (Auto Summary) — 待实现              │
│  ├── 长对话自动压缩为摘要                                │
│  ├── 保留关键决策点和结论                                │
│  ├── 触发: 消息数>20 或 token>4000                      │
│  └── 实现: LLM调用生成摘要                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.3 语义记忆层设计（核心创新点）

不引入向量数据库，用 SQLite FTS5 实现轻量语义搜索：

```python
# app/services/semantic_memory.py

import sqlite3
import json
from datetime import datetime

class SemanticMemoryStore:
    """
    轻量语义记忆存储

    用 SQLite FTS5 实现全文搜索，不需要向量数据库
    每条记忆 = {id, user_id, content, metadata, importance, created_at}

    检索策略:
    1. FTS5 全文匹配（关键词搜索）
    2. importance 排序（重要的记忆优先）
    3. 时间衰减（近期记忆权重更高）

    与 Hermes session_search 对比:
    - Hermes: 在session transcript里grep
    - 这里: 在结构化记忆库里FTS搜索 + 重要性加权
    """

    def __init__(self, db_path: str = ".cache/memory/semantic.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories
            USING FTS5(
                user_id,
                content,
                metadata,
                importance,
                created_at,
                tokenize='unicode61'
            )
        """)

    def add_memory(self, user_id: str, content: str,
                   metadata: dict = None, importance: float = 0.5):
        """添加一条记忆"""
        self.conn.execute(
            "INSERT INTO memories VALUES (?, ?, ?, ?, ?)",
            (user_id, content, json.dumps(metadata or {}),
             str(importance), datetime.now().isoformat())
        )
        self.conn.commit()

    def search(self, user_id: str, query: str, limit: int = 5):
        """
        语义搜索记忆

        用 FTS5 的 BM25 排序 + 时间衰减
        """
        cursor = self.conn.execute("""
            SELECT content, metadata, importance, created_at,
                   rank
            FROM memories
            WHERE user_id = ? AND memories MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (user_id, query, limit))
        return cursor.fetchall()

    def auto_extract_from_session(self, user_id: str,
                                   session_messages: list):
        """
        从会话中自动提取重要记忆

        规则:
        1. 用户明确说的偏好 ("我喜欢...", "记住...")
        2. 重要的气象结论 (CRITICAL/HIGH风险事件)
        3. 决策结果 (GO/NO-GO + 理由)

        不保存:
        1. 闲聊内容
        2. 重复的METAR获取
        3. 中间推理过程
        """
        pass  # 实现时用规则引擎或LLM提取
```

### 3.4 自动摘要机制

当会话消息超过阈值时，自动压缩：

```python
async def maybe_summarize(session, llm_client):
    """会话消息过多时自动摘要"""
    if len(session.messages) <= 20:
        return session

    # 保留最近5条完整消息
    recent = session.messages[-5:]
    older = session.messages[:-5]

    # 用LLM生成摘要
    summary_prompt = f"""请将以下对话压缩为结构化摘要，保留：
    1. 用户关心的机场和天气条件
    2. 关键结论和决策
    3. 用户的偏好信号

    对话内容:
    {[f"[{m.role}] {m.content[:200]}" for m in older]}
    """

    summary = await llm_client.invoke(summary_prompt)

    # 替换旧消息为摘要
    session.messages = [
        Message(role="system", content=f"[历史摘要] {summary}")
    ] + recent

    # 提取重要记忆存入语义层
    semantic_store.auto_extract_from_session(
        session.user_id, older
    )

    return session
```

### 3.5 与Agent的集成方式

在 prompt 中注入相关记忆：

```python
def build_system_prompt_with_memory(role, user_id, query, memory_store):
    """构建带记忆注入的系统提示词"""
    base_prompt = build_system_prompt(role)

    # 1. 用户画像
    user_mem = memory_store.get_user_memory(user_id)
    if user_mem.preferences:
        profile_section = "\n## 用户偏好\n"
        for k, v in user_mem.preferences.items():
            profile_section += f"- {k}: {v}\n"
        base_prompt += profile_section

    # 2. 语义记忆检索
    if query:
        relevant_memories = memory_store.search(user_id, query, limit=3)
        if relevant_memories:
            memory_section = "\n## 相关历史记忆\n"
            for mem in relevant_memories:
                memory_section += f"- {mem[0][:200]} (重要度: {mem[2]})\n"
            base_prompt += memory_section

    return base_prompt
```

### 3.6 三层记忆的协作流程

```
用户消息 "ZSPD能落地吗"
    │
    ▼
┌───────────────────────────────────────────────┐
│ 1. Session Memory → 取最近消息作为对话上下文    │
│    "上一条问的是ZBAA，回答是IFR"               │
├───────────────────────────────────────────────┤
│ 2. User Profile → 注入偏好                     │
│    "role=pilot, aircraft=B737, home_base=ZSPD" │
├───────────────────────────────────────────────┤
│ 3. Semantic Search → 检索相关历史记忆           │
│    "上次ZSPD低能见度时，你建议等TAF更新"        │
├───────────────────────────────────────────────┤
│ 4. Agent ReAct循环开始                         │
│    → fetch_metar(ZSPD) → parse → assess_risk  │
│    → 基于记忆+当前数据给出个性化回答            │
├───────────────────────────────────────────────┤
│ 5. 回答后: 自动提取记忆点                       │
│    "ZSPD ILS CAT I最低标准 DH=60m RVR=550m"   │
│    → 存入 semantic_memory                      │
└───────────────────────────────────────────────┘
```

---

## 四、实施路线图

### Phase 1: 可观测性基础设施（1周）

| 任务 | 工具 | 产出 |
|------|------|------|
| 部署Langfuse | Docker Compose | 自部署LLM追踪平台 |
| 集成Langfuse SDK | `langfuse` pip包 | Agent每次调用自动trace |
| 部署Prometheus+Grafana | Docker Compose | 指标存储+可视化 |
| 定义Prometheus指标 | prometheus_client | 15+核心指标 |
| OTel Collector配置 | opentelemetry-collector | 统一telemetry分发 |
| Grafana Dashboard | JSON Model | 延迟/Token/错误率/工具调用 |

### Phase 2: 自动化评测（1周）

| 任务 | 工具 | 产出 |
|------|------|------|
| 集成DeepEval | pip install deepeval | Agent评测框架 |
| 编写评测用例 | pytest + deepeval | D4幻觉率/D6工具准确率/D7上下文精度 |
| pre-push hook | Shell脚本 | git push前自动跑评测 |
| GitHub Actions | YAML workflow | PR触发评测+结果comment |
| Phoenix集成 | arize-phoenix | 幻觉率趋势看板 |

### Phase 3: 记忆系统升级（1周）

| 任务 | 工具 | 产出 |
|------|------|------|
| SQLite FTS5语义记忆 | 自研 | semantic_memory.py |
| 自动摘要机制 | LLM调用 | 消息压缩+关键点提取 |
| 记忆注入prompt | 修改build_system_prompt | 个性化分析 |
| 自动记忆提取 | 规则引擎 | 从对话中提取记忆点 |
| 用户画像扩展 | 扩展UserMemory | 飞行习惯/决策风格 |

### Phase 4: 告警+集成（3天）

| 任务 | 工具 | 产出 |
|------|------|------|
| AlertManager配置 | Prometheus AlertManager | 4类告警规则 |
| Grafana告警面板 | Grafana | 告警可视化 |
| 端到端验证 | 全链路测试 | 从push到部署的完整闭环 |

---

## 五、核心工具清单汇总

| 类别 | 工具 | 版本/来源 | 用途 |
|------|------|---------|------|
| **评测** | DeepEval | `pip install deepeval` | Agent评测框架 |
| **评测** | Phoenix | `pip install arize-phoenix` | 幻觉检测+质量趋势 |
| **追踪** | Langfuse | Docker自部署 (24.9k⭐) | 全链路LLM追踪 |
| **追踪** | OpenTelemetry SDK | `pip install opentelemetry-*` | 统一telemetry |
| **指标** | Prometheus | Docker | 时间序列存储 |
| **可视化** | Grafana | Docker | Dashboard |
| **告警** | AlertManager | Docker | 阈值告警 |
| **记忆** | SQLite FTS5 | Python内置 | 轻量语义搜索 |
| **CI/CD** | Git pre-push hook | Shell | 评测Gate |
| **CI/CD** | GitHub Actions | YAML | PR评测自动化 |

---

## 六、预期效果

改造完成后，系统能力对比：

| 维度 | 改造前(玩具demo) | 改造后(生产级) |
|------|-----------------|---------------|
| 评测 | 手动跑D1 golden set | 自动化CI gate，push前全量评测 |
| 追踪 | 无 | Langfuse全链路追踪每条请求 |
| 指标 | 无 | Prometheus 15+指标，Grafana可视化 |
| 幻觉检测 | 无 | Phoenix自动检测+趋势图 |
| 告警 | 无 | 4类告警(错误率/延迟/幻觉/评测下降) |
| 记忆 | 基础JSON | 三层记忆(会话+画像+语义) |
| 部署 | 单进程 | Docker Compose一键部署全栈 |
