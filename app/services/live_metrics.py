"""
实时运行指标 — 内存中追踪最近 N 条请求的 token/延迟/provider 信息

给 root 端点和 /api/v3/status 提供实时数据。
不依赖 Prometheus，纯 Python dict + deque。
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


# 最近请求记录（保留最近 200 条）
_MAX_RECORDS = 200
_recent_requests: deque = deque(maxlen=_MAX_RECORDS)
_lock = threading.Lock()

# 累计计数器
_total_requests = 0
_total_success = 0
_total_error = 0
_total_prompt_tokens = 0
_total_completion_tokens = 0
_total_cost_usd = 0.0

# 按 provider/model 统计
_provider_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"requests": 0, "tokens": 0, "errors": 0})


def record_request(
    role: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    iterations: int = 1,
    query: str = "",
    session_id: str = "",
) -> None:
    """记录一次请求的详细信息。"""
    global _total_requests, _total_success, _total_error
    global _total_prompt_tokens, _total_completion_tokens

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    record = {
        "timestamp": now.isoformat(),
        "time_short": now.strftime("%H:%M:%S"),
        "role": role,
        "provider": provider,
        "model": model,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "iterations": iterations,
        "query": query[:80],
        "session_id": session_id,
    }

    with _lock:
        _recent_requests.append(record)
        _total_requests += 1
        if status == "success":
            _total_success += 1
        else:
            _total_error += 1
        _total_prompt_tokens += prompt_tokens
        _total_completion_tokens += completion_tokens

        key = f"{provider}/{model}"
        _provider_stats[key]["requests"] += 1
        _provider_stats[key]["tokens"] += prompt_tokens + completion_tokens
        if status != "success":
            _provider_stats[key]["errors"] += 1


def get_live_status() -> Dict[str, Any]:
    """获取实时运行状态，用于 root 端点展示。"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)

    with _lock:
        recent = list(_recent_requests)
        total = _total_requests
        success = _total_success
        errors = _total_error
        prompt_tok = _total_prompt_tokens
        completion_tok = _total_completion_tokens
        providers = dict(_provider_stats)

    # 最近 10 条请求
    last_10 = recent[-10:] if len(recent) >= 10 else recent
    last_10.reverse()  # 最新的在前

    # 最近 1 小时的请求数
    one_hour_ago = now - timedelta(hours=1)
    recent_1h = [
        r for r in recent
        if datetime.fromisoformat(r["timestamp"]) >= one_hour_ago
    ]

    # 最近延迟
    latencies = [r["latency_ms"] for r in recent_1h if r["latency_ms"] > 0]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0
    p95_latency = round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if len(latencies) >= 2 else avg_latency

    # provider 状态
    provider_list = []
    for key, stats in sorted(providers.items()):
        provider_list.append({
            "provider": key,
            "requests": stats["requests"],
            "tokens": stats["tokens"],
            "errors": stats["errors"],
            "error_rate": round(stats["errors"] / stats["requests"], 3) if stats["requests"] > 0 else 0,
        })

    return {
        "service": "航空气象Agent",
        "version": "3.0.0",
        "mode": "ReAct Agent (LangGraph)",
        "status": "running",
        "uptime_check": now.isoformat(),

        # 累计统计
        "totals": {
            "requests": total,
            "success": success,
            "errors": errors,
            "success_rate": round(success / total, 3) if total > 0 else 0,
            "prompt_tokens": prompt_tok,
            "completion_tokens": completion_tok,
            "total_tokens": prompt_tok + completion_tok,
        },

        # 最近 1 小时
        "recent_1h": {
            "requests": len(recent_1h),
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
        },

        # Provider 统计
        "providers": provider_list,

        # 最近 10 条请求
        "last_requests": last_10,

        # 端点
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "agent_health": "/api/v3/health",
            "chat": "POST /api/v3/chat",
            "chat_stream": "POST /api/v3/chat/stream",
            "sessions": "GET /api/v3/sessions",
            "airports_search": "GET /api/v3/airports/search",
            "metrics": "GET /api/v3/metrics",
            "badcases": "GET /api/v3/badcases",
        },

        # 可观测性
        "observability": {
            "langfuse": "http://localhost:3002",
            "grafana": "http://localhost:3001",
            "prometheus_metrics": "/metrics",
        },
    }
