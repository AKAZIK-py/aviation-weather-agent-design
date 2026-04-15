# 航空气象 Agent — 项目报告

> 生成日期: 2026-04-15
> 项目位置: /Users/twzl/aviation-weather-projects/aviation-weather-agent

---

## 本轮结论摘要

本轮修改目标：
- 搭建完整评测管线（Runner + Scorer + Judge + Badcase）
- 配置三层 Hook 开发工作流
- 建立 CLAUDE.md 项目规范
- 跑通基线 E2E 评测

本轮结果：
- 评测基础设施：已就绪（run_eval.py + scorer.py + judge_eval.py）
- 三层 Hook：已配置并验证
- 评测集：50 条标准集 v2 + 100 条边界集 + 30 条对抗集 + 10 条 hold-out
- Bug 修复：scorer 安全检查误报 + httpx 代理 502
- **基线评测完成**（API 模式，5 条抽样 + Judge）

---

## 指标变化（基线 v2, 5 条抽样 + Scorer 修复后）

| 指标 | 基线 (旧Scorer) | 修复后 | 目标 | 状态 |
|------|----------|---------|-------|------|
| 任务完成率 | 60% | 60% | ≥80% | ❌ 差 20pp |
| 关键信息命中率 | ~7% | **67%** | ≥75% | ⚠️ 差 8pp |
| 输出可用率 (Judge) | 40% | 40% | ≥70% | ❌ 差 30pp |
| 模板化率 (Judge) | 60% | 60% | ≤20% | ❌ 超 40pp |
| 幻觉率 (Judge) | 80% | 80% | ≤10% | ❌ 超 70pp |
| 平均延迟 | 33s | 33s | ≤15s | ❌ 超 2x |

> Scorer 语义模糊匹配修复后，关键信息命中率从 7% 提升至 67%（+60pp）。
> 全量 50 条评测待 venv 修复后执行。

---

## 已知问题（来自 Judge 分析）— 修复进度

| Case | 问题 | 严重度 | 根因 | 修复 |
|------|------|--------|------|------|
| STD_001 | 9999 描述为 "6-10km" 而非 ">10km" | 中 | format_visibility 阈值 | ✅ 已修 (visibility.py) |
| STD_003 | 风向 270° 推荐 02 跑道 | 高 | Agent 凭空猜跑道号 | ✅ 已修 (prompts.py 约束) |
| STD_004 | 获取实时 METAR 替代提供数据 | **严重** | Agent 未使用 metar_raw | ✅ 已修 (prompts.py) |
| STD_005 | get_approach_minima 工具报错 | 中 | 参数传错 (icao→ceiling) | ✅ 已修 (weather_tools.py) |
| 通用 | 模板化输出 (60%) | 高 | markdown 标题+套话 | ✅ PE 收紧 + Scorer 检测增强 |

> 需重启 API 服务器后重新跑全量评测验证修复效果。

---

## 指标变化

| 指标 | Baseline | Current | Delta |
|------|----------|---------|-------|
| 任务完成率 | 待测 | 待测 | - |
| 关键信息命中率 | 待测 | 待测 | - |
| 输出可用率 | 待测 | 待测 | - |
| badcase 回归通过率 | 待测 | 待测 | - |
| 幻觉率 | 待测 | 待测 | - |
| P95 延迟 | 待测 | 待测 | - |

> 注：基线评测需要在真实机器上修复 venv 后执行：
> ```bash
> # 1. 修复 venv
> cd /Users/twzl/aviation-weather-projects/aviation-weather-agent
> rm -rf venv && /usr/local/bin/python3.12 -m venv venv
> venv/bin/pip install -r requirements.txt
>
> # 2. 跑基线
> venv/bin/python scripts/evals/run_eval.py --mode direct --limit 5
> venv/bin/python scripts/evals/run_eval.py --mode direct  # 全量
> ```

---

## 评测管线状态

| 组件 | 状态 | 路径 |
|------|------|------|
| Runner (双模式) | ✅ 就绪 | scripts/evals/run_eval.py |
| Scorer (脚本打分) | ✅ 就绪 + bug 修复 | scripts/evals/scorer.py |
| Judge (Claude Code) | ✅ 就绪 | scripts/evals/judge_eval.py |
| Badcase 管理器 | ✅ 就绪 + 去重 | app/evaluation/badcase_manager.py |
| 标准集 v2 (50 条) | ✅ | eval/datasets/standard_testset_v2.json |
| 边界集 (100 条) | ✅ | eval/datasets/boundary_testset_v1.json |
| 对抗集 (30 条) | ✅ | eval/datasets/adversarial_testset_v1.json |
| Hold-out (10 条) | ✅ | eval/datasets/holdout_testset_v1.json |
| Pre-push hook | ✅ 已更新 | .git/hooks/pre-push → run_eval.py |

---

## 三层 Hook 状态

| 层 | 组件 | 状态 |
|----|------|------|
| L1 安全网 | block_dangerous.sh | ✅ 拦截危险命令 |
| L1 安全网 | protect_sensitive.sh | ✅ 锁住敏感文件 |
| L1 安全网 | ruff format (auto_test.sh) | ✅ 自动格式化 |
| L2 改后即测 | auto_test.sh (关联测试) | ✅ 失败阻断 |
| L2 改后即测 | .pre-commit-config.yaml | ✅ ruff + mypy |
| L2 改后即测 | pr-gate.yml | ✅ PR 强制测试 |
| L2 改后即测 | requesting-code-review | ✅ AI 独立审查 |
| L3 规范+日志 | log_operation.sh | ✅ 操作日志 |
| L3 规范+日志 | auto_commit.sh | ✅ LLM commit message |
| L3 规范+日志 | pre-push hook | ✅ L1+L2 评测 |

---

## 模板化输出专项

待基线评测后填写。

---

## badcase 修复情况

- 本轮新增 badcase：0（尚未跑 E2E）
- 本轮修复 badcase：0
- 累计 badcase 回归通过率：N/A

---

## 附录

- 代码结构：见 `aviation-weather-agent/` 目录树
- 评测集路径：`eval/datasets/`
- badcase 存储路径：`eval/badcases/`
- 评测结果：`eval/results/`
- 运行命令：`python3 -m pytest tests/ -q` / `python scripts/evals/run_eval.py`
- Hook 配置：`.claude/settings.json`
- 项目规范：`CLAUDE.md`
- 工具配置：`ruff.toml`
