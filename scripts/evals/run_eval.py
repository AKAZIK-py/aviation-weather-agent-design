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
RUNNER_VERSION = "0.1.0"
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT_DIR / "eval" / "datasets" / "standard_testset_v2.json"
DEFAULT_OUTPUT = ROOT_DIR / "eval" / "results"

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

    # 3. summary.json
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

    # 写最终产物 (覆盖 case_results.jsonl 为有序版本)
    dataset_path = Path(args.dataset) if not args.regression else ROOT_DIR / "eval" / "badcases"
    write_outputs(out_dir, run_id, args.mode, dataset_path, results, summary, args)

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
    print(f"Gate:       {'PASS' if summary['gate_passed'] else 'FAIL'}")
    print(f"Output:     {out_dir}")
    print("=" * 60)

    # 非零退出码 (CI门禁)
    if not summary["gate_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
