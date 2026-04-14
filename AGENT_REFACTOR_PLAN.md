# 航空气象 Agent 架构重构方案

> 从 Pipeline 架构升级为真正的 Agent 架构
> 目标：LLM 决定流程，人只定义工具和边界

---

## 一、现状 vs 目标

```
现在（Pipeline）：
  用户请求 → Step1(ICAO验证) → Step2(METAR获取) → Step3(正则解析)
           → Step4(关键词选角色) → Step5(LLM美化) → Step6(阈值判风险)
           → Step7(模板报告) → Step8(返回)
  特点：人写死流程，LLM只是"翻译官"

目标（Agent）：
  用户请求 → LLM分析意图 → 自主决定调用哪些工具 → 观察结果 → 决定下一步
           → ... 循环直到信息充分 → 生成最终回答
  特点：LLM是"决策中枢"，工具是手和脚
```

---

## 二、改造范围

### 保留不动的（现有资产复用）
- `app/services/metar_fetcher.py` — METAR获取逻辑
- `app/nodes/parse_metar_node.py` — 正则解析引擎
- `app/nodes/assess_risk_node.py` — 风险评估阈值
- `app/services/role_reporters/` — 角色报告器
- `app/utils/` — 工具函数
- `app/core/config.py` — 配置
- `app/core/llm_client.py` — LLM客户端（需扩展tool_use能力）

### 新增文件
- `app/tools/__init__.py` — 工具定义
- `app/tools/weather_tools.py` — 气象相关工具
- `app/agent/__init__.py`
- `app/agent/graph.py` — LangGraph Agent图
- `app/agent/prompts.py` — Agent系统提示词
- `app/agent/state.py` — Agent状态定义
- `app/api/routes_v3.py` — V3 Agent API

### 大改的
- `app/services/workflow_engine.py` — 增加Agent模式

---

## 三、分阶段实施

### Phase 1: 定义工具层（3天）
把现有服务包装成 LLM 可调用的工具。

### Phase 2: 构建 Agent 图（3天）
用 LangGraph create_react_agent 构建 Agent 循环。

### Phase 3: 简化 Prompt（2天）
从100行固定模板 → 约束边界 + 动态生成。

### Phase 4: 对话记忆（2天）
支持多轮对话，上下文保持。

### Phase 5: V3 API + 兼容（1天）
新端点，向后兼容V1/V2。

---

## 四、详细设计

### 4.1 Phase 1: 工具定义

工具设计原则：
- 每个工具 = 一个确定性的原子操作
- 工具返回结构化数据，不返回自然语言
- 工具失败时返回错误信息，Agent自行决定降级策略
- 复用现有代码，不重写业务逻辑

#### 工具清单

| 工具名 | 输入 | 输出 | 复用来源 |
|--------|------|------|----------|
| fetch_metar | icao: str | raw_metar + metadata | metar_fetcher.py |
| parse_metar | raw_metar: str | 解析后的结构化dict | parse_metar_node.py |
| get_flight_rules | visibility_km, ceiling_ft | VFR/MVFR/IFR/LIFR | parse_metar_node中的规则 |
| assess_risk | metar_parsed: dict | risk_level + factors | assess_risk_node.py |
| get_approach_minima | icao, runway | DH/MDA数据 | utils/approach.py |
| format_visibility | visibility_km | 区间化描述 | utils/visibility.py |

#### 代码实现

见 `app/tools/weather_tools.py`

### 4.2 Phase 2: Agent 图

使用 LangGraph 的 `create_react_agent`，核心循环：

```
用户输入
  ↓
Agent Node (LLM思考)
  ↓ 有工具调用？
  ├─ 是 → Tool Node (执行工具) → 结果返回Agent → 继续思考
  └─ 否 → 返回最终回答
```

关键：ERNIE-4.0 需要适配 tool_calling 格式。
百度千帆V2 API 支持 OpenAI 兼容的 function_calling，但需要验证。

### 4.3 Phase 3: Prompt 改造

之前（100行固定模板）：
```python
system_prompt = """你是资深航线飞行员...
【核心职责】- 评估能见度...
【思维链路】步骤1...步骤2...
【输出格式】严格输出JSON：{...}"""
```

之后（约束边界）：
```python
system_prompt = """你是{role_name}角色的航空顾问。

边界约束：
- 只讨论与{role_focus}直接相关的内容
- 不输出{forbidden_topics}类建议
- 能见度使用区间描述，不暴露精确值
- 风险判断依据ICAO Annex 3标准
- 当需要的数据不全时，主动调用工具获取

根据用户问题，自主决定需要查询哪些数据，给出针对性分析。"""
```

### 4.4 Phase 4: 对话记忆

```python
# 会话级：messages列表
messages = [
    SystemMessage(content=...),
    HumanMessage(content="ZBAA能落地吗"),
    AIMessage(content=..., tool_calls=[...]),
    ToolMessage(content="METAR ZBAA..."),
    AIMessage(content="目前IFR，ILS CAT I可行"),
    HumanMessage(content="那2小时后呢"),  # ← 有上下文了
]

# 用户级：跨会话偏好
user_memory = {
    "aircraft_type": "B737",
    "home_base": "ZSPD",
    "preferred_role": "pilot",
}
```

---

## 五、实施进度

| Phase | 内容 | 状态 | 完成日期 |
|-------|------|------|----------|
| 1. 工具层 | 8个工具（fetch_metar, parse_metar, get_flight_rules, assess_risk, get_approach_minima, format_visibility, fetch_taf, get_full_weather） | ✅ 完成 | 2026-04-14 |
| 2. Agent图 | create_react_agent + 多Provider自动选择 | ✅ 完成 | 之前 |
| 3. Prompt | 约束边界 + 4角色定义 + 动态构建 | ✅ 完成 | 之前 |
| 4. 对话记忆 | Session Store + User Memory（L1内存 + L3文件持久化） | ✅ 完成 | 2026-04-14 |
| 5. V3 API | 8个端点（/chat, /sessions/*, /memory/*, /roles, /health） | ✅ 完成 | 2026-04-14 |

### Phase 4 实现细节
- `app/services/memory.py`: Session/Message/UserMemory 数据模型 + MemoryStore 持久化引擎
- `app/agent/graph.py`: run_agent() 集成 session_id/user_id 参数，自动加载/保存会话
- `app/api/routes_v3.py`: 新增会话管理端点（list/get/delete sessions, get/update user memory）
- 用户记忆自动补充默认值（preferred_role, home_base）

### 工具层补全
- `fetch_taf`: 从 aviationweather.gov 获取 TAF 预报（新增）
- `get_full_weather`: METAR+TAF 一次性获取，任一失败不阻断（新增）
- `app/services/metar_fetcher.py`: 新增 fetch_taf_for_airport() 函数

---

## 六、风险与回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| ERNIE-4.0 tool_calling不稳定 | Agent无法正确调用工具 | 保留V2 Pipeline作为fallback |
| token消耗增加 | 成本上升 | 缓存 + 工具结果截断 |
| 响应延迟增加 | 用户体验 | 设置max_iterations=5 |
| 输出格式不可控 | 前端解析失败 | 仍要求结构化输出，但由LLM自适应 |

---

## 六、验收标准

1. 用户问"ZBAA能落地吗" → Agent自动获取METAR → 解析 → 判断飞行规则 → 给出建议
2. 用户追问"如果2小时后呢" → Agent基于上下文理解"它"指什么 → 继续分析
3. 用户指定角色"我是签派员" → Agent自动调整关注点和输出风格
4. 复杂问题需要多步推理 → Agent自行决定调用多个工具
5. 工具调用失败 → Agent自行降级（如METAR获取失败，提示用户提供原始报文）
