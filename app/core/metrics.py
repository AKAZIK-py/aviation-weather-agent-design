"""
Prometheus 指标定义与记录助手。

覆盖核心运行指标：
- 请求量 / 请求延迟
- Agent 运行次数 / 端到端延迟 / 迭代次数
- Token 使用量
- 工具调用量 / 工具延迟
- 错误计数
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterable, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover - 运行时降级保护
    HAS_PROMETHEUS = False
    logger.warning("prometheus_client 未安装，指标将降级为 no-op")


class NoOpMetric:
    """Prometheus 不可用时的占位对象。"""

    def labels(self, *args, **kwargs):
        return self

    def inc(self, amount: float = 1):
        return None

    def dec(self, amount: float = 1):
        return None

    def observe(self, value: float):
        return None

    def set(self, value: float):
        return None


class AviationMetrics:
    """统一的指标记录入口。"""

    def __init__(self) -> None:
        self.requests_total = self._counter(
            "aviation_agent_requests_total",
            "Total HTTP requests received by the Aviation Weather Agent",
            ["method", "path", "status"],
        )
        self.request_latency_seconds = self._histogram(
            "aviation_agent_request_latency_seconds",
            "HTTP request latency in seconds",
            ["method", "path", "status"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60),
        )
        self.active_requests = self._gauge(
            "aviation_agent_active_requests",
            "In-flight HTTP requests",
        )

        self.agent_runs_total = self._counter(
            "aviation_agent_runs_total",
            "Total Aviation Agent runs",
            ["role", "provider", "status"],
        )
        self.agent_latency_seconds = self._histogram(
            "aviation_agent_run_latency_seconds",
            "Aviation Agent end-to-end run latency in seconds",
            ["role", "provider", "status"],
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120),
        )
        self.agent_iterations = self._histogram(
            "aviation_agent_iterations",
            "Number of tool-augmented reasoning iterations per run",
            ["role", "provider"],
            buckets=(1, 2, 3, 4, 5, 8, 13, 21),
        )

        self.llm_tokens_total = self._counter(
            "aviation_agent_llm_tokens_total",
            "LLM token usage by provider and model",
            ["provider", "model", "token_type"],
        )

        self.tool_calls_total = self._counter(
            "aviation_agent_tool_calls_total",
            "Tool calls executed by the agent",
            ["tool", "status"],
        )
        self.tool_latency_seconds = self._histogram(
            "aviation_agent_tool_latency_seconds",
            "Tool execution latency in seconds",
            ["tool", "status"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
        )

        self.errors_total = self._counter(
            "aviation_agent_errors_total",
            "Errors observed across HTTP, agent, and tool layers",
            ["scope", "error_type"],
        )
        
        # 补全缺失的指标
        self.agent_requests_total = self._counter(
            "agent_requests_total",
            "Total agent requests by role, provider, and status",
            ["role", "provider", "status"],
        )
        self.agent_request_duration_seconds = self._histogram(
            "agent_request_duration_seconds",
            "Agent request duration in seconds",
            ["role", "provider", "status"],
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60),
        )
        self.llm_calls_total = self._counter(
            "llm_calls_total",
            "Total LLM API calls",
            ["provider", "model", "status"],
        )
        self.hallucination_score = self._gauge(
            "hallucination_score",
            "Hallucination detection score (0-1)",
        )
        self.eval_pass_rate = self._gauge(
            "eval_pass_rate",
            "Evaluation pass rate percentage",
        )

    def _existing_collector(self, metric_name: str):
        if not HAS_PROMETHEUS:
            return None
        return getattr(REGISTRY, "_names_to_collectors", {}).get(metric_name)

    def _counter(self, name: str, documentation: str, labelnames: list[str]):
        if not HAS_PROMETHEUS:
            return NoOpMetric()
        existing = self._existing_collector(name)
        if existing:
            return existing
        return Counter(name, documentation, labelnames=labelnames)

    def _gauge(self, name: str, documentation: str):
        if not HAS_PROMETHEUS:
            return NoOpMetric()
        existing = self._existing_collector(name)
        if existing:
            return existing
        return Gauge(name, documentation)

    def _histogram(
        self,
        name: str,
        documentation: str,
        labelnames: list[str],
        buckets: tuple[float, ...],
    ):
        if not HAS_PROMETHEUS:
            return NoOpMetric()
        existing = self._existing_collector(name)
        if existing:
            return existing
        return Histogram(
            name,
            documentation,
            labelnames=labelnames,
            buckets=buckets,
        )

    @contextmanager
    def track_active_request(self):
        self.active_requests.inc()
        try:
            yield
        finally:
            self.active_requests.dec()

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        status = str(status_code)
        self.requests_total.labels(method=method, path=path, status=status).inc()
        self.request_latency_seconds.labels(
            method=method,
            path=path,
            status=status,
        ).observe(duration_seconds)

    def record_agent_run(
        self,
        role: str,
        provider: str,
        status: str,
        duration_seconds: float,
        iterations: int = 0,
    ) -> None:
        self.agent_runs_total.labels(
            role=role,
            provider=provider,
            status=status,
        ).inc()
        self.agent_latency_seconds.labels(
            role=role,
            provider=provider,
            status=status,
        ).observe(duration_seconds)

        if iterations > 0:
            self.agent_iterations.labels(role=role, provider=provider).observe(iterations)

    def record_tool_call(
        self,
        tool: str,
        status: str,
        duration_seconds: float,
        error_type: Optional[str] = None,
    ) -> None:
        self.tool_calls_total.labels(tool=tool, status=status).inc()
        self.tool_latency_seconds.labels(tool=tool, status=status).observe(duration_seconds)
        if error_type:
            self.record_error(scope="tool", error_type=error_type)

    def record_token_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
    ) -> None:
        resolved_total = total_tokens
        if resolved_total is None or resolved_total <= 0:
            resolved_total = max(prompt_tokens, 0) + max(completion_tokens, 0)

        values = {
            "prompt": max(prompt_tokens, 0),
            "completion": max(completion_tokens, 0),
            "total": max(resolved_total, 0),
        }
        for token_type, token_count in values.items():
            if token_count > 0:
                self.llm_tokens_total.labels(
                    provider=provider,
                    model=model,
                    token_type=token_type,
                ).inc(token_count)

    def record_error(self, scope: str, error_type: str) -> None:
        self.errors_total.labels(scope=scope, error_type=error_type).inc()

    def record_agent_request(
        self,
        role: str,
        provider: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """记录 agent 请求（按角色、提供商、状态）"""
        self.agent_requests_total.labels(
            role=role,
            provider=provider,
            status=status,
        ).inc()
        self.agent_request_duration_seconds.labels(
            role=role,
            provider=provider,
            status=status,
        ).observe(duration_seconds)

    def record_llm_call(
        self,
        provider: str,
        model: str,
        status: str,
    ) -> None:
        """记录 LLM API 调用"""
        self.llm_calls_total.labels(
            provider=provider,
            model=model,
            status=status,
        ).inc()

    def set_hallucination_score(self, score: float) -> None:
        """设置幻觉检测分数（0-1）"""
        self.hallucination_score.set(score)

    def set_eval_pass_rate(self, rate: float) -> None:
        """设置评测通过率（百分比）"""
        self.eval_pass_rate.set(rate)


def aggregate_langchain_token_usage(messages: Iterable[Any]) -> Tuple[int, int, int, Optional[str]]:
    """
    从 LangChain / LangGraph 返回消息中聚合 token 用量。

    兼容以下字段：
    - AIMessage.usage_metadata
    - AIMessage.response_metadata.token_usage
    - AIMessage.response_metadata.usage
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    model_name: Optional[str] = None

    for message in messages:
        usage_metadata = getattr(message, "usage_metadata", None) or {}
        response_metadata = getattr(message, "response_metadata", None) or {}
        token_usage = response_metadata.get("token_usage") or response_metadata.get("usage") or {}

        prompt_tokens += int(
            usage_metadata.get("input_tokens")
            or usage_metadata.get("prompt_tokens")
            or token_usage.get("prompt_tokens")
            or token_usage.get("input_tokens")
            or 0
        )
        completion_tokens += int(
            usage_metadata.get("output_tokens")
            or usage_metadata.get("completion_tokens")
            or token_usage.get("completion_tokens")
            or token_usage.get("output_tokens")
            or 0
        )
        total_tokens += int(
            usage_metadata.get("total_tokens")
            or token_usage.get("total_tokens")
            or 0
        )

        if not model_name:
            model_name = (
                response_metadata.get("model_name")
                or response_metadata.get("model")
                or getattr(message, "name", None)
            )

    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens

    return prompt_tokens, completion_tokens, total_tokens, model_name


_metrics: Optional[AviationMetrics] = None


def get_metrics() -> AviationMetrics:
    global _metrics
    if _metrics is None:
        _metrics = AviationMetrics()
    return _metrics


def get_metrics_response() -> tuple[bytes, str]:
    if not HAS_PROMETHEUS:
        return b"# prometheus_client not installed\n", "text/plain; charset=utf-8"
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
