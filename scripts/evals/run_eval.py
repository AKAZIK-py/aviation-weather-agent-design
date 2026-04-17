#!/usr/bin/env python3
"""
航空气象Agent评测Runner

支持 direct / api 双模式执行，产物输出到 eval/results/<run_id>/。
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 版本 & 路径
# ---------------------------------------------------------------------------
RUNNER_VERSION = "0.1.1"
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT_DIR / "eval" / "datasets" / "standard_testset_v2.json"
DEFAULT_OUTPUT = ROOT_DIR / "eval" / "results"

# 确保项目根目录在 sys.path 中（支持直接运行脚本）
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _git_commit() -> str:
    """获取当前 git commit hash (short)"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=ROOT_DIR, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _generate_run_id() -> str:
    """run_<YYYYMMDD_HHMMSS_<4位hash>>"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    h = hashlib.md5(ts.encode()).hexdigest()[:4]
    return f"run_{ts}_{h}"


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    """
    加载测试集，兼容两种格式:
      1. { "metadata": {...}, "cases": [...] }
      2. 扁平数组 [...]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    raise ValueError(f"无法识别的测试集格式: {path}")


def _get_dataset_version(path: Path) -> str:
    """尝试从 metadata 中提取 version"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "metadata" in data:
            return data["metadata"].get("version", "unknown")
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Agent 调用层
# ---------------------------------------------------------------------------

def _call_agent_direct(case: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """
    Direct 模式: 直接 import app.agent.graph.run_agent 调用。
    返回 {"answer": str, "provider": str, "tokens": int|None, "error": None|str}
    """
    import importlib

    try:
        graph_mod = importlib.import_module("app.agent.graph")
        run_agent = graph_mod.run_agent
    except Exception as exc:
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"import_error: {exc}"}

    query = case.get("query", "")
    role = case.get("role", "pilot")
    metar = case.get("metar", "")

    t0 = time.monotonic()
    try:
        # run_agent 是 async 函数
        result = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(
                run_agent(user_query=query, role=role, metar_raw=metar),
                timeout=timeout,
            )
        )
    except RuntimeError:
        # 没有运行中的 event loop，创建新的
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                asyncio.wait_for(
                    run_agent(user_query=query, role=role, metar_raw=metar),
                    timeout=timeout,
                )
            )
        finally:
            loop.close()
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"timeout ({elapsed:.1f}s)"}
    except Exception as exc:
        elapsed = time.monotonic() - t0
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"{type(exc).__name__}: {exc}"}

    elapsed = time.monotonic() - t0

    answer = result.get("answer", "") if isinstance(result, dict) else str(result)
    provider = result.get("provider", "unknown") if isinstance(result, dict) else "unknown"
    tokens = result.get("tokens_used", None) if isinstance(result, dict) else None

    return {"answer": answer, "provider": provider, "tokens": tokens, "elapsed": elapsed, "error": None}


def _call_agent_api(case: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """
    API 模式: POST http://localhost:8000/api/v3/chat
    返回 {"answer": str, "provider": str, "tokens": int|None, "error": None|str}
    """
    import httpx

    url = "http://127.0.0.1:8000/api/v3/chat"
    payload = {
        "query": case.get("query", ""),
        "role": case.get("role", "pilot"),
        "metar_raw": case.get("metar", ""),
    }

    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except httpx.TimeoutException:
        elapsed = time.monotonic() - t0
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"timeout ({elapsed:.1f}s)"}
    except httpx.HTTPStatusError as exc:
        elapsed = time.monotonic() - t0
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"api_error: HTTP {exc.response.status_code}"}
    except Exception as exc:
        elapsed = time.monotonic() - t0
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"{type(exc).__name__}: {exc}"}

    elapsed = time.monotonic() - t0

    answer = body.get("answer", "")
    provider = body.get("provider", "unknown")
    tokens = body.get("token_usage", {}).get("total_tokens", None)

    return {"answer": answer, "provider": provider, "tokens": tokens, "elapsed": elapsed, "error": None}


def call_agent(case: Dict[str, Any], mode: str, timeout: int) -> Dict[str, Any]:
    """统一调度入口"""
    if mode == "direct":
        return _call_agent_direct(case, timeout)
    elif mode == "api":
        return _call_agent_api(case, timeout)
    else:
        return {"answer": "", "provider": "unknown", "tokens": None, "error": f"unknown mode: {mode}"}


# ---------------------------------------------------------------------------
# 打分层
# ---------------------------------------------------------------------------

def _try_import_scorer():
    """
    尝试导入 scorer 模块 (scripts/evals/scorer.py)。
    返回 score_case(case, output) -> dict 或 None。
    """
    try:
        scorer_path = Path(__file__).parent / "scorer.py"
        if scorer_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("scorer", str(scorer_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "score_case"):
                return mod.score_case
        # 也尝试包导入
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from scripts.evals.scorer import score_case  # type: ignore
        return score_case
    except Exception:
        return None


def _try_import_judge():
    """
    尝试导入 judge 模块 (scripts/evals/judge_eval.py)。
    返回 judge_case(case, output, timeout) -> dict 或 None。
    """
    try:
        judge_path = Path(__file__).parent / "judge_eval.py"
        if judge_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("judge_eval", str(judge_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "judge_case"):
                return mod.judge_case
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from scripts.evals.judge_eval import judge_case  # type: ignore
        return judge_case
    except Exception:
        return None


def _try_import_normal_scorer():
    """尝试导入 normal_scorer 模块。返回 score_case_normal 或 None。"""
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from scripts.evals.normal_scorer import score_case_normal  # type: ignore
        return score_case_normal
    except Exception:
        return None


def _try_import_expert_scorer():
    """尝试导入 expert_scorer 模块。返回 score_case_expert 或 None。"""
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from scripts.evals.expert_scorer import score_case_expert  # type: ignore
        return score_case_expert
    except Exception:
        return None


def _try_import_iaa_checker():
    """尝试导入 iaa_checker 模块。返回 compute_iaa 或 None。"""
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        from scripts.evals.iaa_checker import compute_iaa  # type: ignore
        return compute_iaa
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 失败分类
# ---------------------------------------------------------------------------

def classify_error(error: Optional[str], answer: str) -> str:
    """
    错误分类:
      - infra_failure: 超时/网络/导入异常
      - schema_failure: 输出格式异常 (空输出但无error)
      - model_failure: Agent输出了但质量不行 (由scorer判定)
      - None (通过)
    """
    if error is None:
        if not answer or not answer.strip():
            return "schema_failure"
        return None  # 正常
    # 有 error → infra_failure
    if "timeout" in error.lower() or "import_error" in error.lower() or "api_error" in error.lower():
        return "infra_failure"
    return "infra_failure"


# ---------------------------------------------------------------------------
# 单条执行
# ---------------------------------------------------------------------------

def run_single_case(
    case: Dict[str, Any],
    mode: str,
    timeout: int,
    score_fn=None,
    judge_fn=None,
) -> Dict[str, Any]:
    """
    执行单条 case，返回结构化结果。
    失败隔离：任何异常都被捕获并记录。
    """
    case_id = case.get("id", "unknown")
    start = time.monotonic()

    result = call_agent(case, mode, timeout)
    elapsed = result.get("elapsed", time.monotonic() - start)

    answer = result.get("answer", "")
    provider = result.get("provider", "unknown")
    tokens = result.get("tokens")
    error = result.get("error")

    # 分类错误
    error_type = classify_error(error, answer)

    # 打分 (脚本)
    score_info = None
    if score_fn and error_type is None:
        try:
            score_info = score_fn(case, answer)
        except Exception as exc:
            score_info = {"error": f"scorer_exception: {exc}"}

    # Judge (LLM-as-Judge, 可选)
    judge_info = None
    if judge_fn and error_type is None and answer and answer.strip():
        try:
            judge_info = judge_fn(case, answer, timeout=min(timeout, 60))
        except Exception as exc:
            judge_info = {"error": f"judge_exception: {exc}"}

    record = {
        "case_id": case_id,
        "input": {
            "query": case.get("query", ""),
            "role": case.get("role", "pilot"),
            "metar": case.get("metar", ""),
        },
        "output": answer,
        "latency_ms": round(elapsed * 1000),
        "tokens": tokens,
        "provider": provider,
        "error": error,
        "error_type": error_type,
        "score": score_info,
        "judge": judge_info,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    return record


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从 case_results 计算汇总指标"""
    total = len(results)
    passed = sum(1 for r in results if r.get("error_type") is None)
    infra_failures = sum(1 for r in results if r.get("error_type") == "infra_failure")
    schema_failures = sum(1 for r in results if r.get("error_type") == "schema_failure")
    model_failures = sum(1 for r in results if r.get("error_type") == "model_failure")

    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else avg_latency

    scores = [
        r["score"] for r in results
        if r.get("score") and isinstance(r["score"], dict) and "overall_score" in r["score"]
    ]
    avg_score = round(sum(s["overall_score"] for s in scores) / len(scores), 4) if scores else None

    # 门禁: pass_rate >= 90%
    pass_rate = passed / total if total > 0 else 0
    gate_passed = pass_rate >= 0.90

    # Judge 汇总 (如果有)
    judge_results = [
        r["judge"] for r in results
        if r.get("judge") and isinstance(r["judge"], dict) and "usable" in r["judge"]
    ]
    judge_usable_rate = None
    judge_hallucination_rate = None
    judge_template_rate = None
    if judge_results:
        n = len(judge_results)
        judge_usable_rate = round(sum(1 for j in judge_results if j["usable"]) / n, 4)
        judge_hallucination_rate = round(sum(1 for j in judge_results if j.get("hallucination")) / n, 4)
        judge_template_rate = round(sum(1 for j in judge_results if j.get("is_template")) / n, 4)

    # === 新增: 4+2+3 专家指标汇总 ===

    # 飞行规则准确率
    fr_scores = [
        s for s in scores
        if "flight_rules_matched" in s
    ]
    fr_matched = sum(1 for s in fr_scores if s["flight_rules_matched"])
    fr_total = len(fr_scores)
    flight_rules_accuracy = round(fr_matched / fr_total, 4) if fr_total > 0 else None
    flight_rules_gate = (flight_rules_accuracy or 0) >= 0.95

    # 风险评估准确率
    risk_scores = [
        s for s in scores
        if "risk_assessment_matched" in s
    ]
    risk_matched = sum(1 for s in risk_scores if s["risk_assessment_matched"])
    risk_total = len(risk_scores)
    risk_assessment_accuracy = round(risk_matched / risk_total, 4) if risk_total > 0 else None
    risk_assessment_gate = (risk_assessment_accuracy or 0) >= 0.90

    # 安全边界覆盖率
    safety_scores = [
        s for s in scores
        if "safety_coverage_passed" in s
    ]
    critical_cases = sum(
        1 for r in results
        if r.get("score") and isinstance(r["score"], dict)
        and r["score"].get("details", {}).get("safety_coverage", {}).get("is_critical_case")
    )
    critical_passed = sum(
        1 for r in results
        if r.get("score") and isinstance(r["score"], dict)
        and r["score"].get("details", {}).get("safety_coverage", {}).get("correctly_marked")
    )
    safety_coverage_rate = round(critical_passed / critical_cases, 4) if critical_cases > 0 else 1.0
    safety_coverage_gate = safety_coverage_rate == 1.0 if critical_cases > 0 else True

    return {
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(pass_rate, 4),
        "infra_failures": infra_failures,
        "schema_failures": schema_failures,
        "model_failures": model_failures,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
        "p95_latency_ms": p95_latency,
        "avg_score": avg_score,
        "judge_usable_rate": judge_usable_rate,
        "judge_hallucination_rate": judge_hallucination_rate,
        "judge_template_rate": judge_template_rate,
        "gate_passed": gate_passed,
        # 专家指标
        "flight_rules_accuracy": flight_rules_accuracy,
        "flight_rules_gate": flight_rules_gate,
        "risk_assessment_accuracy": risk_assessment_accuracy,
        "risk_assessment_gate": risk_assessment_gate,
        "safety_coverage_rate": safety_coverage_rate,
        "safety_coverage_gate": safety_coverage_gate,
        "critical_cases": critical_cases,
        "expert_gates_passed": all([flight_rules_gate, risk_assessment_gate, safety_coverage_gate]),
    }


# ---------------------------------------------------------------------------
# 产物写入
# ---------------------------------------------------------------------------

def write_outputs(
    out_dir: Path,
    run_id: str,
    mode: str,
    dataset_path: Path,
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
    args: argparse.Namespace,
    normal_scores: Optional[List[Dict[str, Any]]] = None,
    expert_scores: Optional[List[Dict[str, Any]]] = None,
    iaa_result: Optional[Dict[str, Any]] = None,
):
    """写入所有产物到 out_dir"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. manifest.json
    manifest = {
        "run_id": run_id,
        "runner_version": RUNNER_VERSION,
        "git_commit": _git_commit(),
        "dataset_version": _get_dataset_version(dataset_path),
        "dataset_path": str(dataset_path),
        "mode": mode,
        "model": os.environ.get("EVAL_MODEL", "auto"),
        "provider": os.environ.get("EVAL_PROVIDER", "auto"),
        "judge_enabled": args.judge,
        "llm_scoring_enabled": getattr(args, "llm_scoring", False),
        "total_cases": len(results),
        "timeout": args.timeout,
        "created_at": datetime.datetime.now().isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 2. case_results.jsonl
    with open(out_dir / "case_results.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 2b. normal_scores.jsonl (if available)
    if normal_scores:
        with open(out_dir / "normal_scores.jsonl", "w", encoding="utf-8") as f:
            for s in normal_scores:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # 2c. expert_scores.jsonl (if available)
    if expert_scores:
        with open(out_dir / "expert_scores.jsonl", "w", encoding="utf-8") as f:
            for s in expert_scores:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # 3. summary.json — merge all scores
    if normal_scores or expert_scores:
        summary["llm_scoring"] = {}
        if normal_scores:
            n = len(normal_scores)
            if n > 0:
                summary["llm_scoring"]["normal"] = {
                    "task_complete_rate": round(sum(s.get("task_complete", 0) for s in normal_scores) / n, 4),
                    "key_info_hit_rate": round(sum(s.get("key_info_hit", 0) for s in normal_scores) / n, 4),
                    "usable_rate": round(sum(s.get("usable", 0) for s in normal_scores) / n, 4),
                    "template_rate": round(sum(s.get("template", 0) for s in normal_scores) / n, 4),
                    "hallucination_rate": round(sum(s.get("hallucination", 0) for s in normal_scores) / n, 4),
                    "total_scored": n,
                }
        if expert_scores:
            n = len(expert_scores)
            if n > 0:
                summary["llm_scoring"]["expert"] = {
                    "flight_rules_accurate_rate": round(sum(s.get("flight_rules_accurate", 0) for s in expert_scores) / n, 4),
                    "risk_accurate_rate": round(sum(s.get("risk_accurate", 0) for s in expert_scores) / n, 4),
                    "safety_covered_rate": round(sum(s.get("safety_covered", 0) for s in expert_scores) / n, 4),
                    "total_scored": n,
                }
        if iaa_result:
            summary["llm_scoring"]["iaa"] = iaa_result

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 4. summary.md (人类可读报告)
    md_lines = [
        f"# 评测报告: {run_id}",
        "",
        f"- 模式: `{mode}`",
        f"- 数据集: `{dataset_path.name}`",
        f"- Commit: `{manifest['git_commit']}`",
        f"- 时间: {manifest['created_at']}",
        "",
        "## 汇总",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 总用例数 | {summary['total_cases']} |",
        f"| 通过数 | {summary['passed']} |",
        f"| 通过率 | {summary['pass_rate']:.1%} |",
        f"| 基础设施失败 | {summary['infra_failures']} |",
        f"| 格式失败 | {summary['schema_failures']} |",
        f"| 模型失败 | {summary['model_failures']} |",
        f"| 平均延迟 | {summary['avg_latency_ms']}ms |",
        f"| P95延迟 | {summary['p95_latency_ms']}ms |",
        f"| 最大延迟 | {summary['max_latency_ms']}ms |",
    ]
    if summary["avg_score"] is not None:
        md_lines.append(f"| 平均分 | {summary['avg_score']} |")

    if summary.get("judge_usable_rate") is not None:
        md_lines.extend([
            "",
            "## Judge 评估 (Claude Code)",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 输出可用率 | {summary['judge_usable_rate']:.1%} |",
            f"| 幻觉率 | {summary['judge_hallucination_rate']:.1%} |",
            f"| 模板化率 | {summary['judge_template_rate']:.1%} |",
        ])

    # LLM 普通评分
    llm_scoring = summary.get("llm_scoring", {})
    if llm_scoring.get("normal"):
        ns = llm_scoring["normal"]
        md_lines.extend([
            "",
            "## LLM 普通评分 (Claude Code)",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 任务完成率 | {ns['task_complete_rate']:.1%} |",
            f"| 关键信息命中率 | {ns['key_info_hit_rate']:.1%} |",
            f"| 输出可用率 | {ns['usable_rate']:.1%} |",
            f"| 模板化率 | {ns['template_rate']:.1%} |",
            f"| 幻觉率 | {ns['hallucination_rate']:.1%} |",
            f"| 评分数 | {ns['total_scored']} |",
        ])

    # LLM 专家评分
    if llm_scoring.get("expert"):
        es = llm_scoring["expert"]
        md_lines.extend([
            "",
            "## LLM 专家评分 (Claude Code + ICAO Annex 3)",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 飞行规则准确率 | {es['flight_rules_accurate_rate']:.1%} |",
            f"| 风险评估准确率 | {es['risk_accurate_rate']:.1%} |",
            f"| 安全边界覆盖率 | {es['safety_covered_rate']:.1%} |",
            f"| 评分数 | {es['total_scored']} |",
        ])

    # IAA 抽检
    if llm_scoring.get("iaa"):
        iaa = llm_scoring["iaa"]
        md_lines.extend([
            "",
            "## IAA 抽检 (Inter-Annotator Agreement)",
            "",
            f"- 状态: **{iaa['status']}**",
            f"- {iaa['message']}",
            f"- Cohen's Kappa: {iaa['kappa']}",
            f"- 抽样数: {iaa['sample_size']} / {iaa['total_cases']}",
            f"- 观察一致率: {iaa['agreement_rate']:.1%}",
        ])
        if iaa.get("divergent_cases"):
            md_lines.extend([
                f"- 分歧案例数: {len(iaa['divergent_cases'])}",
            ])

    md_lines.extend([
        "",
        "## 门禁结果",
        "",
        f"**{'PASS' if summary['gate_passed'] else 'FAIL'}** (阈值: 通过率 >= 90%)",
        "",
        "## 失败用例",
        "",
    ])

    failures = [r for r in results if r.get("error_type")]
    if failures:
        md_lines.append("| case_id | error_type | error |")
        md_lines.append("|---------|-----------|-------|")
        for r in failures:
            err = (r.get("error") or "").replace("|", "\\|")[:60]
            md_lines.append(f"| {r['case_id']} | {r['error_type']} | {err} |")
    else:
        md_lines.append("无失败用例。")

    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


# ---------------------------------------------------------------------------
# 回归模式: 加载 badcases
# ---------------------------------------------------------------------------

def load_regression_cases(badcases_dir: Path) -> List[Dict[str, Any]]:
    """
    加载 badcases.jsonl 中 fixed=false 的 case。
    """
    badcases_file = badcases_dir / "badcases.jsonl"
    if not badcases_file.exists():
        print(f"[warn] badcases.jsonl not found at {badcases_file}, skipping regression.")
        return []

    cases = []
    with open(badcases_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            bc = json.loads(line)
            if bc.get("fixed", False):
                continue
            # 转成标准 case 格式
            inp = bc.get("input", {})
            cases.append({
                "id": bc.get("case_id", "unknown"),
                "query": inp.get("query", ""),
                "role": inp.get("role", "pilot"),
                "metar": inp.get("metar", ""),
            })
    return cases


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="航空气象Agent评测Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/evals/run_eval.py                          # 默认 direct 模式
  python scripts/evals/run_eval.py --mode api               # API 模式
  python scripts/evals/run_eval.py --limit 5                # 只跑前5条
  python scripts/evals/run_eval.py --filter pilot           # 只跑 pilot 角色
  python scripts/evals/run_eval.py --regression             # 回归模式跑 badcases
  python scripts/evals/run_eval.py --timeout 60 --judge     # 60s超时 + 开启LLM Judge
""",
    )
    parser.add_argument("--mode", choices=["direct", "api"], default="direct",
                        help="执行模式 (default: direct)")
    parser.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET),
                        help=f"测试集路径 (default: {DEFAULT_DATASET})")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help=f"输出目录 (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--limit", type=int, default=None,
                        help="只跑前N条用例")
    parser.add_argument("--filter", type=str, default=None,
                        help="按角色过滤 (pilot/dispatcher/forecaster/ground_crew)")
    parser.add_argument("--judge", action="store_true", default=False,
                        help="开启Claude Code Judge (Phase 2, 预留接口)")
    parser.add_argument("--regression", action="store_true", default=False,
                        help="回归模式: 跑 badcases.jsonl 中 fixed=false 的 case")
    parser.add_argument("--timeout", type=int, default=30,
                        help="每条用例超时秒数 (default: 30)")
    parser.add_argument("--llm-scoring", action="store_true", default=False,
                        help="开启 LLM 普通+专家评分 + IAA 抽检")

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # 决定数据来源
    if args.regression:
        badcases_dir = ROOT_DIR / "eval" / "badcases"
        cases = load_regression_cases(badcases_dir)
        if not cases:
            print("[info] No unfixed badcases found. Nothing to run.")
            return
        print(f"[regression] Loaded {len(cases)} unfixed badcases.")
    else:
        dataset_path = Path(args.dataset)
        if not dataset_path.exists():
            print(f"[error] Dataset not found: {dataset_path}", file=sys.stderr)
            sys.exit(1)
        cases = _load_dataset(dataset_path)
        print(f"[dataset] Loaded {len(cases)} cases from {dataset_path.name}")

    # 过滤
    if args.filter:
        before = len(cases)
        cases = [c for c in cases if c.get("role") == args.filter]
        print(f"[filter] role={args.filter}: {before} -> {len(cases)}")

    # 限制条数
    if args.limit is not None and args.limit > 0:
        cases = cases[:args.limit]
        print(f"[limit] Running first {len(cases)} cases")

    # 生成 run_id & 输出目录
    run_id = _generate_run_id()
    out_dir = Path(args.output) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # 导入 scorer
    score_fn = _try_import_scorer()
    if score_fn:
        print("[scorer] Loaded scorer module.")
    else:
        print("[scorer] No scorer module found, skipping scoring.")

    # 导入 judge (可选)
    judge_fn = None
    if args.judge:
        judge_fn = _try_import_judge()
        if judge_fn:
            print("[judge] Loaded Claude Code Judge module.")
        else:
            print("[judge] Judge module not found, skipping judge.")

    # 逐条执行
    results: List[Dict[str, Any]] = []
    total = len(cases)
    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx}")
        print(f"[{idx}/{total}] Running {case_id} (mode={args.mode}) ...", end=" ", flush=True)

        record = run_single_case(case, args.mode, args.timeout, score_fn, judge_fn)
        results.append(record)

        et = record.get("error_type")
        status = "OK" if et is None else et
        latency = record.get("latency_ms", 0)
        print(f"{status} ({latency}ms)")

        # 逐条写入 (增量保存, 防止中断丢数据)
        with open(out_dir / "case_results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 汇总
    summary = compute_summary(results)

    # LLM 评分 (可选)
    normal_scores = None
    expert_scores = None
    iaa_result = None

    if getattr(args, "llm_scoring", False):
        # 构建评分用 case_data
        scoring_cases = []
        for r in results:
            if r.get("error_type") is not None:
                continue
            case_id = r.get("case_id", "unknown")
            inp = r.get("input", {})
            output = r.get("output", "")
            if not output or not output.strip():
                continue
            # 查找原始 case 数据
            orig_case = None
            for c in cases:
                if c.get("id") == case_id:
                    orig_case = c
                    break
            scoring_cases.append({
                "case_id": case_id,
                "query": inp.get("query", ""),
                "role": inp.get("role", "pilot"),
                "metar": inp.get("metar", ""),
                "metar_text": inp.get("metar", ""),
                "agent_output": output,
                "output": output,
                "expected_key_info": orig_case.get("expected_key_info", []) if orig_case else [],
                "expected_flight_rules": orig_case.get("expected_flight_rules", "") if orig_case else "",
                "expected_risk_level": orig_case.get("expected_risk_level", "") if orig_case else "",
            })

        if scoring_cases:
            # 普通评分
            normal_fn = _try_import_normal_scorer()
            if normal_fn:
                print(f"\n[llm_scoring] Running normal scorer on {len(scoring_cases)} cases ...")
                normal_scores = []
                for idx, sc in enumerate(scoring_cases, 1):
                    cid = sc.get("case_id", f"case_{idx}")
                    print(f"  [normal] [{idx}/{len(scoring_cases)}] {cid} ...", flush=True)
                    try:
                        result = normal_fn(sc)
                    except Exception as exc:
                        result = {"case_id": cid, "error": str(exc)}
                    normal_scores.append(result)
                print(f"[llm_scoring] Normal scoring done: {len(normal_scores)} results.")
            else:
                print("[llm_scoring] normal_scorer not available, skipping.")

            # 专家评分
            expert_fn = _try_import_expert_scorer()
            if expert_fn:
                print(f"\n[llm_scoring] Running expert scorer on {len(scoring_cases)} cases ...")
                expert_scores = []
                for idx, sc in enumerate(scoring_cases, 1):
                    cid = sc.get("case_id", f"case_{idx}")
                    print(f"  [expert] [{idx}/{len(scoring_cases)}] {cid} ...", flush=True)
                    try:
                        result = expert_fn(sc)
                    except Exception as exc:
                        result = {"case_id": cid, "error": str(exc)}
                    expert_scores.append(result)
                print(f"[llm_scoring] Expert scoring done: {len(expert_scores)} results.")
            else:
                print("[llm_scoring] expert_scorer not available, skipping.")

            # IAA 抽检
            if normal_scores and expert_scores:
                iaa_fn = _try_import_iaa_checker()
                if iaa_fn:
                    print("\n[llm_scoring] Running IAA checker ...")
                    try:
                        iaa_result = iaa_fn(normal_scores, expert_scores)
                        print(f"[llm_scoring] IAA: {iaa_result.get('message', 'done')}")
                    except Exception as exc:
                        iaa_result = {"status": "ERROR", "message": f"IAA check failed: {exc}"}
                else:
                    print("[llm_scoring] iaa_checker not available, skipping.")
        else:
            print("[llm_scoring] No valid cases for LLM scoring.")

    # 写最终产物 (覆盖 case_results.jsonl 为有序版本)
    dataset_path = Path(args.dataset) if not args.regression else ROOT_DIR / "eval" / "badcases"
    write_outputs(out_dir, run_id, args.mode, dataset_path, results, summary, args,
                  normal_scores=normal_scores, expert_scores=expert_scores, iaa_result=iaa_result)

    # 打印结果
    print()
    print("=" * 60)
    print(f"Run ID:     {run_id}")
    print(f"Total:      {summary['total_cases']}")
    print(f"Passed:     {summary['passed']}")
    print(f"Pass Rate:  {summary['pass_rate']:.1%}")
    print(f"Avg Latency:{summary['avg_latency_ms']}ms")
    if summary["avg_score"] is not None:
        print(f"Avg Score:  {summary['avg_score']}")
    if summary.get("judge_usable_rate") is not None:
        print(f"Judge Usable:    {summary['judge_usable_rate']:.1%}")
        print(f"Judge Halluc:    {summary['judge_hallucination_rate']:.1%}")
        print(f"Judge Template:  {summary['judge_template_rate']:.1%}")
    # 专家指标
    if summary.get("flight_rules_accuracy") is not None:
        print(f"Flight Rules:    {summary['flight_rules_accuracy']:.1%} (gate: >=95% {'PASS' if summary['flight_rules_gate'] else 'FAIL'})")
    if summary.get("risk_assessment_accuracy") is not None:
        print(f"Risk Assess:     {summary['risk_assessment_accuracy']:.1%} (gate: >=90% {'PASS' if summary['risk_assessment_gate'] else 'FAIL'})")
    if summary.get("safety_coverage_rate") is not None:
        print(f"Safety Cover:    {summary['safety_coverage_rate']:.1%} (gate: =100% {'PASS' if summary['safety_coverage_gate'] else 'FAIL'})")
    print(f"Gate:       {'PASS' if summary['gate_passed'] else 'FAIL'}")
    print(f"Expert Gates:   {'PASS' if summary.get('expert_gates_passed') else 'FAIL'}")
    # LLM 评分结果
    llm_scoring = summary.get("llm_scoring", {})
    if llm_scoring.get("normal"):
        ns = llm_scoring["normal"]
        print(f"\n--- LLM 普通评分 ---")
        print(f"  Task Complete:  {ns['task_complete_rate']:.1%}")
        print(f"  Key Info Hit:   {ns['key_info_hit_rate']:.1%}")
        print(f"  Usable:         {ns['usable_rate']:.1%}")
        print(f"  Template:       {ns['template_rate']:.1%}")
        print(f"  Hallucination:  {ns['hallucination_rate']:.1%}")
    if llm_scoring.get("expert"):
        es = llm_scoring["expert"]
        print(f"\n--- LLM 专家评分 ---")
        print(f"  Flight Rules:   {es['flight_rules_accurate_rate']:.1%}")
        print(f"  Risk Accurate:  {es['risk_accurate_rate']:.1%}")
        print(f"  Safety Cover:   {es['safety_covered_rate']:.1%}")
    if llm_scoring.get("iaa"):
        iaa = llm_scoring["iaa"]
        print(f"\n--- IAA 抽检 ---")
        print(f"  {iaa['message']}")
        print(f"  Kappa: {iaa['kappa']}")
    print(f"Output:     {out_dir}")
    print("=" * 60)

    # 非零退出码 (CI门禁)
    if not summary["gate_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
