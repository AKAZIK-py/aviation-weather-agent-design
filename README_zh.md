# 航空气象 Agent

[English](./README.md) | 中文

基于大语言模型的航空气象报文（METAR）智能分析系统，严格遵循 ICAO Annex 3 标准，面向四类角色（飞行员、签派员、预报员、地勤机务）提供个性化天气分析报告。

## ✨ 核心特性

- **ICAO 标准合规**: 严格遵循 ICAO Annex 3 标准进行 METAR 解析和飞行规则判定
- **多角色分析**: 飞行员、签派员、气象预报员、地勤四种专业视角
- **动态风险引擎**: 基于能见度、云底高、风况的动态风险权重评估
- **LangGraph 工作流**: 声明式多节点工作流编排
- **全链路可观测性**: Prometheus + Grafana + Langfuse 三级监控
- **E2E Chat UI**: 实时对话界面 + SSE 流式输出 + 自动评测
- **4+2 评测体系**: 任务完成率、关键信息命中率、输出可用率、Badcase 回归通过率 + 幻觉率、延迟/成本

## 🏗️ 技术栈

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

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker (可选，用于监控栈)

### 安装

```bash
# 克隆仓库
git clone https://github.com/AKAZIK-py/aviation-weather-agent-design.git
cd aviation-weather-agent-design

# 后端安装
cd aviation-weather-agent
cp .env.example .env
# 编辑 .env 填入你的 API Key
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 前端安装
cd ../aviation-weather-frontend
npm install
```

### 配置

编辑 `aviation-weather-agent/.env`:

```bash
# LLM Provider (至少配置一个)
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 或百度千帆
QIANFAN_AK=your_ak
QIANFAN_SK=your_sk

# 可观测性 (可选)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3002
```

### 启动服务

```bash
# 启动后端 (端口 8000)
cd aviation-weather-agent
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 启动前端 (端口 3000)
cd aviation-weather-frontend
npm run dev
```

访问 http://localhost:3000 开始使用。

### 运行测试

```bash
cd aviation-weather-agent
source venv/bin/activate

# 单元测试
python -m pytest tests/ -q

# 全量评测
python scripts/evals/run_eval.py --mode api --dataset standard
```

### 启动监控栈 (可选)

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

- Grafana: http://localhost:3001
- Langfuse: http://localhost:3002
- Prometheus: http://localhost:9090

## 📁 项目结构

```
aviation-weather-agent-design/
├── aviation-weather-agent/         # 核心 Agent (FastAPI + LangGraph)
│   ├── app/
│   │   ├── agent/                  # LangGraph ReAct 循环
│   │   │   ├── graph.py            # 工作流定义
│   │   │   └── prompts.py          # PE V3 约束边界
│   │   ├── api/                    # FastAPI 路由
│   │   │   ├── routes_v3.py        # SSE 流式接口
│   │   │   └── schemas.py          # 请求/响应模型
│   │   ├── core/                   # 核心引擎
│   │   │   ├── llm_client.py       # 多 provider LLM 客户端
│   │   │   ├── config.py           # 配置管理
│   │   │   └── workflow.py         # 工作流引擎
│   │   ├── nodes/                  # LangGraph 节点
│   │   ├── prompts/                # PE 模板
│   │   ├── services/               # 业务服务
│   │   │   ├── live_metrics.py     # 实时指标采集
│   │   │   ├── auto_evaluator.py   # 自动评测
│   │   │   ├── eval_store.py       # 评测结果存储
│   │   │   ├── memory.py           # SQLite FTS5 记忆
│   │   │   └── role_reporters/     # 4 角色输出策略
│   │   ├── tools/                  # Agent 工具
│   │   │   └── weather_tools.py    # METAR 解析/风险评估
│   │   ├── utils/                  # 工具函数
│   │   └── evaluation/             # 评测框架
│   └── tests/                      # 测试套件
├── aviation-weather-frontend/      # Next.js 15 前端
│   └── src/
│       ├── app/                    # 页面路由
│       ├── components/             # UI 组件
│       │   ├── chat/               # 聊天界面
│       │   ├── metrics/            # 指标仪表板
│       │   └── sidebar/            # 侧边栏
│       └── lib/                    # 工具库
├── aviation-weather-ai/            # 评测模块
├── eval/                           # 评测数据集
│   ├── datasets/                   # 三层评测集
│   ├── badcases/                   # 失败样本
│   └── results/                    # 评测结果
├── scripts/                        # 脚本工具
│   ├── evals/                      # 评测 Runner
│   └── hooks/                      # 三层 Hook
├── monitoring/                     # 监控配置
├── CLAUDE.md                       # 项目规范
├── EVOLUTION_PLAN.md               # 进化方案
├── EXECUTION_PLAN.md               # 执行计划
└── PROJECT_REPORT.md               # 项目报告
```

## 📊 评测指标

### 主指标 (Agent 价值)

| 指标 | 当前 | 目标 | 状态 |
|------|------|------|------|
| 任务完成率 | 98% | ≥80% | ✅ 超目标 18pp |
| 关键信息命中率 | 68% | ≥75% | ⚠️ 差 7pp |
| 输出可用率 | 98% | ≥70% | ✅ 超目标 28pp |
| Badcase 回归通过率 | 100% | ≥95% | ✅ 首次建立即达标 |

### 辅助指标 (护栏)

| 指标 | 当前 | 目标 | 状态 |
|------|------|------|------|
| 幻觉率 | <5% | ≤10% | ✅ 大幅改善 |
| P95 延迟 | 21.3s | ≤15s | ⚠️ 仍超 6.3s |

### 全量评测结果

```
标准集 (50条): 通过率 98% (49/50), avg_score 0.68, P95 21335ms, Gate PASS
对抗集 (30条): 通过率 100% (30/30), avg_score 0.55, P95 20196ms, Gate PASS
Hold-out (10条): 通过率 100% (10/10), avg_score 0.79, P95 22845ms, Gate PASS
```

## 🔧 API 端点

### 后端 (FastAPI)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | HTML 实时仪表板 |
| `/api/v3/chat/stream` | POST | SSE 流式对话 |
| `/api/v3/evaluate` | POST | 触发评测 |
| `/api/v3/metrics` | GET | 实时指标 |
| `/api/v3/badcases` | GET | Badcase 列表 |
| `/health` | GET | 健康检查 |

### 前端

| 页面 | 路径 | 说明 |
|------|------|------|
| 对话 | `/` | 实时对话界面 |
| 指标 | `/` (切换 Tab) | 评测指标仪表板 |

## 🛠️ 开发工作流

### 三层 Hook

**第一层：安全网**
- `block_dangerous.sh`: 拦截 rm -rf / force push
- `protect_sensitive.sh`: 锁住 .env / credentials
- 自动格式化: ruff format

**第二层：改后即测**
- `auto_test.sh`: 关联测试失败阻断
- `.pre-commit-config.yaml`: ruff + mypy
- `pr-gate.yml`: PR 强制测试通过

**第三层：规范+日志**
- `log_operation.sh`: 操作日志
- `auto_commit.sh`: LLM commit message
- `pre-push hook`: L1 标准集 + L2 badcase 回归

## 📈 监控

### 可观测性栈

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

## 🤝 贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发规范

- Python 3.12，类型注解必须
- 异步优先: FastAPI + httpx/aiohttp
- Pydantic v2 做数据验证
- 用 ruff 做 lint + format
- 测试用 pytest + pytest-asyncio

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 📞 联系

- 项目地址: https://github.com/AKAZIK-py/aviation-weather-agent-design
- 问题反馈: [Issues](https://github.com/AKAZIK-py/aviation-weather-agent-design/issues)

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [LangGraph](https://langchain-ai.github.io/langgraph/) - 声明式工作流编排
- [Next.js](https://nextjs.org/) - React 框架
- [Tailwind CSS](https://tailwindcss.com/) - 实用优先 CSS
- [shadcn/ui](https://ui.shadcn.com/) - 可定制 UI 组件
- [Langfuse](https://langfuse.com/) - LLM 可观测性
