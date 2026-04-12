# Aviation Weather Agent

基于 ICAO Annex 3 标准的航空气象智能分析系统，提供多角色（飞行员/签派/气象员/地勤）视角的气象风险评估与决策支持。

## 项目结构

```
aviation-weather-agent-design/
├── aviation-weather-agent/     # 核心 Agent (FastAPI + LangGraph + ERNIE-4.0)
│   ├── app/
│   │   ├── api/               # REST API 路由 (v1/v2)
│   │   ├── core/              # 核心引擎 (LLM客户端/工作流/熔断器)
│   │   ├── nodes/             # LangGraph 工作流节点
│   │   ├── services/          # 业务服务 (METAR解析/风险评估/角色报告)
│   │   ├── utils/             # 工具类 (能见度/云底/动态权重)
│   │   ├── prompts/           # LLM 提示词模板
│   │   ├── evaluation/        # D1 评测框架 (golden set + 幻觉检测)
│   │   ├── data/              # 机场数据
│   │   └── models/            # 数据模型
│   └── .env.example           # 环境变量模板
├── aviation-weather-frontend/ # 前端 (Next.js 15 + Tailwind)
├── aviation-weather-backend/  # 后端备选实现
├── aviation-weather-ui/       # 轻量级前端 (Vanilla JS)
├── aviation-weather-ai/       # AI 评测模块
└── 交付报告_航空气象Agent*.md  # 项目交付文档
```

## 核心特性

- **ICAO 标准合规**: 严格遵循 ICAO Annex 3 标准进行 METAR 解析和飞行规则判定
- **多角色分析**: 飞行员、签派员、气象预报员、地勤四种专业视角
- **动态风险引擎**: 基于能见度、云底高、风况的动态风险权重评估
- **LangGraph 工作流**: 声明式多节点工作流编排
- **D1 评测框架**: 内置 golden set 测试集，支持幻觉检测和可靠性审计

## 快速开始

### 环境配置

```bash
cd aviation-weather-agent
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 启动服务

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端启动

```bash
cd aviation-weather-frontend
npm install
npm run dev
```

## API 端点

- `POST /api/v1/weather/analyze` - 气象分析 (v1)
- `POST /api/v2/weather/analyze` - 增强版气象分析 (v2)
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/airports/{icao}` - 机场信息

## 技术栈

| 组件 | 技术选型 |
|------|----------|
| Agent 引擎 | FastAPI + LangGraph + 百度 ERNIE-4.0 |
| METAR 解析 | 自研 ICAO-compliant 解析器 |
| 风险评估 | 动态权重引擎 + 规则引擎 |
| 前端 | Next.js 15 + Tailwind CSS + shadcn/ui |
| 评测 | D1 框架 + Golden Set + 幻觉检测 |

## License

MIT
