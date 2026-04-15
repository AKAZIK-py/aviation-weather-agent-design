# CLAUDE.md — Aviation Weather Agent 项目规范

## 项目概要
航空气象 AI Agent。用户选角色（飞行员/签派/预报员/地勤）→ 问天气 → Agent 调 API → 给建议。
核心链路：用户问"虹桥能降吗" → 调 METAR → 按角色给自然语言建议（不是模板报告）。

## 目录结构
```
app/
├── agent/        # LangGraph ReAct 循环，核心推理逻辑
├── api/          # FastAPI 路由
├── core/         # 配置、依赖注入
├── data/         # 数据层
├── evaluation/   # 评测数据集
├── models/       # Pydantic 数据模型
├── nodes/        # LangGraph 节点
├── prompts/      # PE (Prompt Engineering) 模板
├── services/     # 业务逻辑层
│   └── role_reporters/  # 4 个角色的输出策略
├── tools/        # Agent 可调用工具
├── utils/        # 工具函数
tests/            # pytest 测试
eval/
├── datasets/     # 三层评测集 (standard/boundary/adversarial)
├── badcases/     # 失败样本 (BC_*.json)
├── golden_answers/  # 人工标注答案
├── results/      # 评测运行结果
scripts/
├── hooks/        # Claude Code 三层 Hook 脚本
├── evals/        # 评测运行脚本
monitoring/       # Prometheus + Grafana + AlertManager 配置
```

## 代码规范
- Python 3.12，类型注解必须
- 异步优先：FastAPI + httpx/aiohttp
- Pydantic v2 做数据验证
- 用 ruff 做 lint + format（不用 flake8/black）
- 测试用 pytest + pytest-asyncio

## 命名约定
- 文件：snake_case.py
- 类：PascalCase
- 函数/变量：snake_case
- 常量：UPPER_SNAKE_CASE
- 测试文件：test_<module>.py

## 评测体系
- 4 个主指标：任务完成率、关键信息命中率、输出可用率、badcase 回归通过率
- 2 个辅助指标：幻觉率、延迟/成本
- 三层评测集防过拟合：L1 标准集(50条/git tag 锁)、L2 边界集(100条)、L3 对抗集(30条)
- badcase 自动沉淀 → 回归验证

## PE 设计原则
- V3 约束边界模式：只定义"你是谁"+"你关注什么"+"你别碰什么"
- 不写死思维链路步骤，不写死输出格式
- 角色影响关注点，不影响输出格式
- 温度按任务类型配置：解析0.0 / 决策0.0 / 分类0.3 / 生成0.7 / Judge 0.0

## Hook 系统 (三层)
Claude Code 开发时的保护机制，不是 Agent 功能。

### 第一层：安全网
- block_dangerous.sh：拦截 rm -rf / force push 等危险命令
- protect_sensitive.sh：锁住 .env / credentials / SSH keys
- 自动格式化：改 .py 后自动 ruff format

### 第二层：改后即测
- auto_test.sh：改 .py 后自动跑关联测试，失败阻断
- .pre-commit-config.yaml：提交前 ruff lint + mypy
- .github/workflows/pr-gate.yml：PR 强制测试通过

### 第三层：规范+日志
- log_operation.sh：每步操作写 .claude/logs/operations.jsonl
- auto_commit.sh：git diff → LLM 生成 commit message
- pre-push hook：L1 标准集 + L2 badcase 回归

## 禁止事项
- 不要注释掉报错让代码跑起来
- 不要把密钥/ token 写进代码
- 不要用固定模板输出天气报告
- 不要绕过测试失败直接 push

## 启动命令
```bash
# 后端
cd aviation-weather-agent && source venv/bin/activate && uvicorn app.api.main:app --reload --port 8000

# 前端
cd aviation-weather-frontend && npm run dev  # port 3000

# 测试
python -m pytest tests/ -q

# 格式化
ruff format app/ tests/
ruff check app/ tests/ --fix
```

## 环境变量
- DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL
- 见 .env.example（实际密钥在 .env，受 hook 保护）
