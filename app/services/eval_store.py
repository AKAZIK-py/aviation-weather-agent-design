"""评测结果存储 — 追踪每次对话的评测分数 + 聚合指标"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict

def _get_store_dir() -> Path:
    """懒加载存储目录路径（避免 import-time CWD 冻结）。"""
    d = Path(os.getcwd()) / ".cache" / "eval_store"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_results_file() -> Path:
    return _get_store_dir() / "results.jsonl"


def _parse_key_info_hit(key_info_hit: str) -> float:
    """将 '6/21' 格式转为命中率 0.0~1.0。"""
    try:
        parts = key_info_hit.split("/")
        hits = int(parts[0])
        total = int(parts[1])
        return hits / total if total > 0 else 0.0
    except (ValueError, IndexError, ZeroDivisionError):
        return 0.0


def record_eval_result(
    session_id: str,
    query: str,
    role: str,
    eval_scores: dict,
    processing_time_ms: float,
    tool_calls_count: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    provider: str = "",
    model: str = "",
) -> None:
    """追加一条评测结果到 JSONL 文件。"""
    results_file = _get_results_file()

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    record = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "query": query[:200],
        "role": role,
        "task_complete": eval_scores.get("task_complete", False),
        "key_info_hit": eval_scores.get("key_info_hit", "0/0"),
        "output_usable": eval_scores.get("output_usable", False),
        "hallucination_rate": eval_scores.get("hallucination_rate", 0.0),
        "processing_time_ms": round(processing_time_ms, 1),
        "tool_calls_count": tool_calls_count,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "provider": provider,
        "model": model,
        "is_badcase": (
            not eval_scores.get("task_complete", False)
            or eval_scores.get("hallucination_rate", 0.0) > 0.3
        ),
    }

    with open(results_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_results(days: int = 7) -> List[Dict[str, Any]]:
    """加载最近 N 天的评测结果。"""
    results_file = _get_results_file()
    if not results_file.exists():
        return []

    tz = timezone(timedelta(hours=8))
    cutoff = datetime.now(tz) - timedelta(days=days)
    results: List[Dict[str, Any]] = []

    with open(results_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = datetime.fromisoformat(record.get("timestamp", ""))
                if ts >= cutoff:
                    results.append(record)
            except (json.JSONDecodeError, ValueError):
                continue

    return results


def get_aggregated_metrics(days: int = 7) -> Dict[str, Any]:
    """聚合最近 N 天的评测指标。

    返回:
    {
        "total_requests": 150,
        "success_rate": 0.96,
        "avg_latency_ms": 3200,
        "task_completion_rate": 0.98,
        "key_info_avg_hits": 5.2,
        "output_usability_rate": 0.97,
        "hallucination_rate": 0.02,
        "badcase_count": 3,
        "role_distribution": {"pilot": 60, "dispatcher": 30, ...},
        "daily_trend": [
            {"date": "2026-04-19", "requests": 20, "task_completion": 0.95, ...},
            ...
        ]
    }
    """
    results = _load_results(days)
    total = len(results)

    if total == 0:
        return {
            "total_requests": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0,
            "task_completion_rate": 0.0,
            "key_info_avg_hits": 0.0,
            "output_usability_rate": 0.0,
            "hallucination_rate": 0.0,
            "badcase_count": 0,
            "role_distribution": {},
            "daily_trend": [],
        }

    # 基础聚合
    task_complete_count = sum(1 for r in results if r.get("task_complete", False))
    output_usable_count = sum(1 for r in results if r.get("output_usable", False))
    badcase_count = sum(1 for r in results if r.get("is_badcase", False))
    total_latency = sum(r.get("processing_time_ms", 0) for r in results)
    total_hallucination = sum(r.get("hallucination_rate", 0) for r in results)

    # Token 聚合
    total_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in results)
    total_completion_tokens = sum(r.get("completion_tokens", 0) for r in results)
    total_tokens = total_prompt_tokens + total_completion_tokens

    # Provider 分布
    provider_dist: Dict[str, int] = defaultdict(int)
    for r in results:
        p = r.get("provider", "unknown") or "unknown"
        provider_dist[p] += 1

    # 关键信息命中率平均值
    key_info_rates = [
        _parse_key_info_hit(r.get("key_info_hit", "0/0")) for r in results
    ]
    avg_key_info = sum(key_info_rates) / total if total > 0 else 0.0

    # 角色分布
    role_distribution: Dict[str, int] = defaultdict(int)
    for r in results:
        role = r.get("role", "unknown")
        role_distribution[role] += 1

    # 按天聚合趋势
    daily_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        ts = r.get("timestamp", "")
        try:
            date_str = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        except ValueError:
            continue
        daily_data[date_str].append(r)

    daily_trend = []
    for date_str in sorted(daily_data.keys(), reverse=True):
        day_records = daily_data[date_str]
        day_total = len(day_records)
        day_task_complete = sum(
            1 for r in day_records if r.get("task_complete", False)
        )
        day_hallucination = sum(
            r.get("hallucination_rate", 0) for r in day_records
        )
        day_latency = sum(
            r.get("processing_time_ms", 0) for r in day_records
        )

        day_tokens = sum(r.get("total_tokens", 0) for r in day_records)
        daily_trend.append(
            {
                "date": date_str,
                "requests": day_total,
                "task_completion": round(
                    day_task_complete / day_total if day_total > 0 else 0.0, 3
                ),
                "hallucination": round(
                    day_hallucination / day_total if day_total > 0 else 0.0, 3
                ),
                "avg_latency_ms": round(
                    day_latency / day_total if day_total > 0 else 0.0, 1
                ),
                "total_tokens": day_tokens,
                "avg_tokens": round(day_tokens / day_total) if day_total > 0 else 0,
            }
        )

    return {
        "total_requests": total,
        "success_rate": round(
            (total - badcase_count) / total if total > 0 else 0.0, 3
        ),
        "avg_latency_ms": round(total_latency / total if total > 0 else 0.0, 1),
        "task_completion_rate": round(
            task_complete_count / total if total > 0 else 0.0, 3
        ),
        "key_info_avg_hits": round(avg_key_info, 3),
        "output_usability_rate": round(
            output_usable_count / total if total > 0 else 0.0, 3
        ),
        "hallucination_rate": round(
            total_hallucination / total if total > 0 else 0.0, 3
        ),
        "badcase_count": badcase_count,
        "role_distribution": dict(role_distribution),
        "daily_trend": daily_trend,
        # Token 统计
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "avg_tokens_per_request": round(total_tokens / total) if total > 0 else 0,
        "provider_distribution": dict(provider_dist),
    }
