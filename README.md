# Aviation Weather Agent

English | [中文](./README_zh.md)

An intelligent aviation weather analysis system based on large language models, strictly following ICAO Annex 3 standards, providing personalized weather analysis reports for four roles (pilot, dispatcher, forecaster, ground crew).

## ✨ Core Features

- **ICAO Standards Compliance**: Strict adherence to ICAO Annex 3 for METAR parsing and flight rule determination
- **Multi-Role Analysis**: Four professional perspectives - pilot, dispatcher, forecaster, and ground crew
- **Dynamic Risk Engine**: Dynamic risk weight assessment based on visibility, cloud base height, and wind conditions
- **LangGraph Workflow**: Declarative multi-node workflow orchestration
- **Full-Chain Observability**: Three-level monitoring with Prometheus + Grafana + Langfuse
- **E2E Chat UI**: Real-time chat interface + SSE streaming + automatic evaluation
- **4+2 Evaluation System**: Task completion rate, key information hit rate, output usability rate, badcase regression pass rate + hallucination rate, latency/cost

## 🏗️ Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Engine | FastAPI + LangGraph + Baidu ERNIE-4.0 |
| LLM Client | DeepSeek / ERNIE-4.0 (multi-provider fallback) |
| METAR Parsing | Self-developed ICAO-compliant parser |
| Risk Assessment | Dynamic weight engine + rule engine |
| Frontend | Next.js 15 + Tailwind CSS + shadcn/ui |
| Evaluation | 4+2 metrics system + three-tier evaluation sets |
| Observability | Prometheus + Grafana + Langfuse + Live Metrics |
| Development Tools | Claude Code + Codex + Three-layer Hooks |

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (optional, for monitoring stack)

### Installation

```bash
# Clone repository
git clone https://github.com/AKAZIK-py/aviation-weather-agent-design.git
cd aviation-weather-agent-design

# Backend installation
cd aviation-weather-agent
cp .env.example .env
# Edit .env to add your API keys
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend installation
cd ../aviation-weather-frontend
npm install
```

### Configuration

Edit `aviation-weather-agent/.env`:

```bash
# LLM Provider (configure at least one)
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Or Baidu Qianfan
QIANFAN_AK=your_ak
QIANFAN_SK=your_sk

# Observability (optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3002
```

### Start Services

```bash
# Start backend (port 8000)
cd aviation-weather-agent
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Start frontend (port 3000)
cd aviation-weather-frontend
npm run dev
```

Visit http://localhost:3000 to start using.

### Run Tests

```bash
cd aviation-weather-agent
source venv/bin/activate

# Unit tests
python -m pytest tests/ -q

# Full evaluation
python scripts/evals/run_eval.py --mode api --dataset standard
```

### Start Monitoring Stack (Optional)

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

- Grafana: http://localhost:3001
- Langfuse: http://localhost:3002
- Prometheus: http://localhost:9090

## 📁 Project Structure

```
aviation-weather-agent-design/
├── aviation-weather-agent/         # Core Agent (FastAPI + LangGraph)
│   ├── app/
│   │   ├── agent/                  # LangGraph ReAct loop
│   │   │   ├── graph.py            # Workflow definition
│   │   │   └── prompts.py          # PE V3 constraint boundary
│   │   ├── api/                    # FastAPI routes
│   │   │   ├── routes_v3.py        # SSE streaming endpoint
│   │   │   └── schemas.py          # Request/response models
│   │   ├── core/                   # Core engine
│   │   │   ├── llm_client.py       # Multi-provider LLM client
│   │   │   ├── config.py           # Configuration management
│   │   │   └── workflow.py         # Workflow engine
│   │   ├── nodes/                  # LangGraph nodes
│   │   ├── prompts/                # PE templates
│   │   ├── services/               # Business services
│   │   │   ├── live_metrics.py     # Real-time metrics collection
│   │   │   ├── auto_evaluator.py   # Automatic evaluation
│   │   │   ├── eval_store.py       # Evaluation result storage
│   │   │   ├── memory.py           # SQLite FTS5 memory
│   │   │   └── role_reporters/     # 4 role output strategies
│   │   ├── tools/                  # Agent tools
│   │   │   └── weather_tools.py    # METAR parsing/risk assessment
│   │   ├── utils/                  # Utility functions
│   │   └── evaluation/             # Evaluation framework
│   └── tests/                      # Test suite
├── aviation-weather-frontend/      # Next.js 15 frontend
│   └── src/
│       ├── app/                    # Page routes
│       ├── components/             # UI components
│       │   ├── chat/               # Chat interface
│       │   ├── metrics/            # Metrics dashboard
│       │   └── sidebar/            # Sidebar
│       └── lib/                    # Utility libraries
├── aviation-weather-ai/            # Evaluation module
├── eval/                           # Evaluation datasets
│   ├── datasets/                   # Three-tier evaluation sets
│   ├── badcases/                   # Failed samples
│   └── results/                    # Evaluation results
├── scripts/                        # Script tools
│   ├── evals/                      # Evaluation runner
│   └── hooks/                      # Three-layer hooks
├── monitoring/                     # Monitoring configuration
├── CLAUDE.md                       # Project specification
├── EVOLUTION_PLAN.md               # Evolution plan
├── EXECUTION_PLAN.md               # Execution plan
└── PROJECT_REPORT.md               # Project report
```

## 📊 Evaluation Metrics

### Main Metrics (Agent Value)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Task Completion Rate | 98% | ≥80% | ✅ Exceeds by 18pp |
| Key Information Hit Rate | 68% | ≥75% | ⚠️ 7pp short |
| Output Usability Rate | 98% | ≥70% | ✅ Exceeds by 28pp |
| Badcase Regression Pass Rate | 100% | ≥95% | ✅ Established and met |

### Auxiliary Metrics (Guardrails)

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Hallucination Rate | <5% | ≤10% | ✅ Greatly improved |
| P95 Latency | 21.3s | ≤15s | ⚠️ 6.3s over target |

### Full Evaluation Results

```
Standard Set (50 cases): Pass rate 98% (49/50), avg_score 0.68, P95 21335ms, Gate PASS
Adversarial Set (30 cases): Pass rate 100% (30/30), avg_score 0.55, P95 20196ms, Gate PASS
Hold-out Set (10 cases): Pass rate 100% (10/10), avg_score 0.79, P95 22845ms, Gate PASS
```

## 🔧 API Endpoints

### Backend (FastAPI)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | HTML real-time dashboard |
| `/api/v3/chat/stream` | POST | SSE streaming chat |
| `/api/v3/evaluate` | POST | Trigger evaluation |
| `/api/v3/metrics` | GET | Real-time metrics |
| `/api/v3/badcases` | GET | Badcase list |
| `/health` | GET | Health check |

### Frontend

| Page | Path | Description |
|------|------|-------------|
| Chat | `/` | Real-time chat interface |
| Metrics | `/` (Tab switch) | Evaluation metrics dashboard |

## 🛠️ Development Workflow

### Three-Layer Hooks

**Layer 1: Safety Net**
- `block_dangerous.sh`: Block rm -rf / force push
- `protect_sensitive.sh`: Lock .env / credentials
- Auto-format: ruff format

**Layer 2: Test on Code Landing**
- `auto_test.sh`: Related test failure blocking
- `.pre-commit-config.yaml`: ruff + mypy
- `pr-gate.yml`: PR mandatory test passing

**Layer 3: Standards + Logging**
- `log_operation.sh`: Operation logging
- `auto_commit.sh`: LLM commit message
- `pre-push hook`: L1 standard set + L2 badcase regression

## 📈 Monitoring

### Observability Stack

| Component | Port | Purpose |
|-----------|------|---------|
| FastAPI | 8000 | Backend API + HTML Dashboard |
| Next.js | 3000 | Frontend Chat UI |
| Langfuse | 3002 | LLM Trace tracking |
| Grafana | 3001 | Prometheus metrics visualization |
| Prometheus | 9090 | Metrics collection |
| AlertManager | 9093 | Alert management |

### Monitoring Metrics

- **Agent Layer**: Task completion rate, key information hit rate, output usability rate, hallucination rate
- **Infrastructure**: Request latency P50/P95/P99, Token usage, Provider switch count
- **Business Layer**: Query distribution by role, airport popularity, flight rule distribution

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create Pull Request

### Development Standards

- Python 3.12, type annotations required
- Async-first: FastAPI + httpx/aiohttp
- Pydantic v2 for data validation
- Use ruff for lint + format
- Use pytest + pytest-asyncio for testing

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 📞 Contact

- Project URL: https://github.com/AKAZIK-py/aviation-weather-agent-design
- Issue Feedback: [Issues](https://github.com/AKAZIK-py/aviation-weather-agent-design/issues)

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - High-performance web framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Declarative workflow orchestration
- [Next.js](https://nextjs.org/) - React framework
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS
- [shadcn/ui](https://ui.shadcn.com/) - Customizable UI components
- [Langfuse](https://langfuse.com/) - LLM observability
