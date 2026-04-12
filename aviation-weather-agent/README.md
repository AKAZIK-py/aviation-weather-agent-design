# 航空气象Agent - 后端服务

基于 **LangGraph + 百度千帆ERNIE-4.0 + FastAPI** 的智能航空气象分析系统。

## 📋 项目概述

本项目是航空气象Agent的核心后端服务，采用 **规则+LLM混合三层架构**，实现METAR报文智能解析、角色识别、风险评估和个性化解释生成。

### 核心特性

- ✅ **METAR智能解析**：自动解析标准METAR格式，提取关键气象要素
- ✅ **角色识别**：基于用户问题自动识别四类角色（空管/地勤/运控/机务）
- ✅ **多维度风险评估**：结合规则引擎和LLM判断风险等级
- ✅ **安全边界检查**：Critical风险自动触发人工干预
- ✅ **个性化解释生成**：根据角色生成定制化自然语言解释
- ✅ **推理轨迹追踪**：完整记录决策过程，便于调试和评测

### 评测指标体系

| 指标 | 目标值 | 说明 |
|------|--------|------|
| D1 - 规则映射准确率 | ≥95% | METAR解析规则正确性 |
| D2 - 角色匹配准确率 | ≥85% | 用户角色识别准确度 |
| D3 - 安全边界覆盖率 | =100% | Critical风险必须干预 |
| D4 - 幻觉率 | ≤5% | LLM输出事实准确性 |
| D5 - 越权率 | =0% | 严格角色权限控制 |

## 🏗️ 项目架构

```
航空气象Agent
├── 规则层（确定性逻辑）
│   ├── METAR解析规则（ICAO标准）
│   ├── 风险评估规则（RISK_THRESHOLDS）
│   └── 安全边界规则（SAFETY_RULES）
├── LLM层（语义理解）
│   ├── 角色识别（classify_role_node）
│   └── 解释生成（generate_explanation_node）
└── 工作流编排（LangGraph）
    ├── parse_metar_node → 解析METAR
    ├── classify_role_node → 识别角色
    ├── assess_risk_node → 评估风险
    ├── check_safety_node → 安全检查
    └── generate_explanation_node → 生成解释
```

## 📁 项目结构

```
aviation-weather-agent/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                 # 配置管理
│   │   ├── workflow_state.py         # 工作流状态定义
│   │   ├── workflow.py               # LangGraph工作流图
│   │   └── llm_client.py             # 百度千帆LLM客户端
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                # Pydantic数据模型
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── parse_metar_node.py       # METAR解析节点
│   │   ├── classify_role_node.py     # 角色识别节点
│   │   ├── assess_risk_node.py       # 风险评估节点
│   │   ├── check_safety_node.py      # 安全边界检查节点
│   │   └── generate_explanation_node.py # 解释生成节点
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                 # API路由
│   │   └── schemas.py                # API请求/响应模型
│   ├── main.py                       # FastAPI主应用
│   └── __init__.py
├── tests/
│   ├── test_nodes/                   # 节点单元测试
│   ├── test_api/                     # API集成测试
│   └── test_evaluation/              # D1-D5评测脚本
├── datasets/
│   ├── metar_samples.json            # METAR样本数据
│   ├── test_cases_d1.json            # D1测试用例
│   ├── test_cases_d2.json            # D2测试用例
│   ├── test_cases_d3.json            # D3测试用例
│   ├── test_cases_d4.json            # D4测试用例
│   └── test_cases_d5.json            # D5测试用例
├── docs/
│   ├── backend_test_plan.md          # 后端测试方案
│   ├── langgraph_flow_design.md      # LangGraph流程设计
│   ├── rule_database.md              # 规则数据库
│   └── evaluation_implementation_plan.md # 评测实施方案
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- 百度千帆API密钥（API Key + Secret Key）

### 2. 安装依赖

```bash
cd aviation-weather-agent
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件，填入百度千帆API密钥
```

```env
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret_key
BAIDU_MODEL_NAME=ERNIE-4.0-8K
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

### 4. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/api/v1/health

## 📡 API端点

### POST /api/v1/analyze

分析METAR天气报文

**请求示例：**

```json
{
  "metar_raw": "ZBAA 110530Z 35008MPS 9999 FEW040 12/M05 Q1018 NOSIG",
  "user_query": "当前天气适合起降吗？",
  "session_id": "session-123"
}
```

**响应示例：**

```json
{
  "success": true,
  "metar_parsed": {
    "icao_code": "ZBAA",
    "observation_time": "2024-01-11T05:30:00Z",
    "wind_direction": 350,
    "wind_speed": 8,
    "visibility": 9999,
    "clouds": [{"amount": "FEW", "height": 4000}],
    "temperature": 12,
    "dewpoint": -5,
    "qnh": 1018,
    "flight_rules": "VFR"
  },
  "detected_role": "空管",
  "risk_level": "LOW",
  "risk_factors": [],
  "explanation": "当前北京首都机场天气条件良好，VFR飞行规则适用...",
  "intervention_required": false,
  "llm_calls": 1,
  "processing_time_ms": 1250.5
}
```

### GET /api/v1/health

健康检查

### GET /api/v1/metrics

服务指标（Prometheus格式）

## 🧪 测试

### 单元测试

```bash
pytest tests/test_nodes/ -v
```

### API集成测试

```bash
pytest tests/test_api/ -v
```

### D1-D5评测

```bash
python tests/test_evaluation/run_evaluation.py
```

## 📊 监控与日志

### 日志格式

```
2024-01-11 05:30:00 - app.api.routes - INFO - Processing request: session=session-123
2024-01-11 05:30:01 - app.api.routes - INFO - Request completed: role=空管, risk=LOW, time=1250.50ms
```

### 关键指标

- `requests_total`: 请求总数
- `requests_success`: 成功请求数
- `avg_processing_time_ms`: 平均处理时间
- `llm_calls_total`: LLM调用总次数

## 🔧 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| BAIDU_API_KEY | 必填 | 百度千帆API Key |
| BAIDU_SECRET_KEY | 必填 | 百度千帆Secret Key |
| BAIDU_MODEL_NAME | ERNIE-4.0-8K | 模型名称 |
| LLM_TEMPERATURE | 0.7 | LLM温度参数 |
| LLM_MAX_TOKENS | 2048 | 最大输出token数 |
| DEBUG | false | 调试模式 |

## 📝 开发进度

- [x] 项目架构设计
- [x] 配置管理模块
- [x] 数据模型定义
- [x] LangGraph工作流状态
- [x] 5个核心节点实现
  - [x] parse_metar_node
  - [x] classify_role_node
  - [x] assess_risk_node
  - [x] check_safety_node
  - [x] generate_explanation_node
- [x] LangGraph工作流图定义
- [x] FastAPI服务端点
- [ ] 前端界面原型（Next.js 15）
- [ ] 部署配置（Cloudflare Workers）

## 📚 参考文档

- [LangGraph官方文档](https://langchain-ai.github.io/langgraph/)
- [百度千帆API文档](https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html)
- [FastAPI官方文档](https://fastapi.tiangolo.com/)
- [ICAO METAR标准](https://www.icao.int/publications/pages/publication.aspx?docnum=8632)

## 📄 许可证

MIT License

## 👨‍💻 作者

航空AI团队 - 航空气象Agent项目
