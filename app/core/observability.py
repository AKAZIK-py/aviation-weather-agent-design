"""
可观测性基础设施
- Prometheus 指标收集
- LangGraph 节点耗时追踪
- 结构化日志关联
"""
import time
import logging
import functools
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Prometheus client 导入（可选降级）
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus_client not installed, metrics will be no-ops")


class NoOpMetric:
    """NoOp指标（当Prometheus不可用时）"""
    def labels(self, **kwargs):
        return self
    def observe(self, value):
        pass
    def inc(self, amount=1):
        pass
    def dec(self, amount=1):
        pass
    def set(self, value):
        pass


class AgentMetrics:
    """
    航空气象Agent Prometheus 指标集合
    
    指标列表:
    - llm_call_duration_seconds: LLM调用耗时 (Histogram)
    - metar_analysis_total: METAR分析总数 (Counter)
    - cache_hit_total: 缓存命中计数 (Counter)
    - safety_intervention_total: 安全干预计数 (Counter)
    - workflow_duration_seconds: 工作流端到端耗时 (Histogram)
    - workflow_node_duration_seconds: 各节点耗时 (Histogram)
    - active_requests: 当前活跃请求数 (Gauge)
    """
    
    def __init__(self):
        if HAS_PROMETHEUS:
            self._init_prometheus_metrics()
        else:
            self._init_noop_metrics()
    
    def _init_prometheus_metrics(self):
        """初始化Prometheus指标"""
        # LLM调用耗时
        self.llm_call_duration = Histogram(
            "llm_call_duration_seconds",
            "LLM API call duration in seconds",
            labelnames=["model", "node", "status"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )
        
        # LLM调用总数
        self.llm_call_total = Counter(
            "llm_call_total",
            "Total LLM API calls",
            labelnames=["model", "status"],
        )
        
        # METAR分析计数
        self.metar_analysis_total = Counter(
            "metar_analysis_total",
            "Total METAR analyses performed",
            labelnames=["flight_rules", "risk_level"],
        )
        
        # 缓存命中计数
        self.cache_hit_total = Counter(
            "cache_hit_total",
            "Cache hit count by level",
            labelnames=["cache_level", "result"],  # level: L1/L2/L3, result: hit/miss
        )
        
        # 安全干预计数
        self.safety_intervention_total = Counter(
            "safety_intervention_total",
            "Safety interventions triggered",
            labelnames=["risk_type", "action"],
        )
        
        # 工作流耗时
        self.workflow_duration = Histogram(
            "workflow_duration_seconds",
            "End-to-end workflow duration in seconds",
            labelnames=["success"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
        )
        
        # 节点耗时
        self.node_duration = Histogram(
            "workflow_node_duration_seconds",
            "Individual node execution duration",
            labelnames=["node_name", "status"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
        )
        
        # 活跃请求
        self.active_requests = Gauge(
            "active_requests",
            "Number of active requests being processed",
        )
        
        # METAR获取计数
        self.metar_fetch_total = Counter(
            "metar_fetch_total",
            "METAR data fetch attempts",
            labelnames=["source", "status"],  # source: api/simulated
        )
        
        # Circuit breaker 状态
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
            labelnames=["breaker_name"],
        )
        
        logger.info("Prometheus metrics initialized")
    
    def _init_noop_metrics(self):
        """初始化NoOp指标（降级模式）"""
        noop = NoOpMetric()
        self.llm_call_duration = noop
        self.llm_call_total = noop
        self.metar_analysis_total = noop
        self.cache_hit_total = noop
        self.safety_intervention_total = noop
        self.workflow_duration = noop
        self.node_duration = noop
        self.active_requests = noop
        self.metar_fetch_total = noop
        self.circuit_breaker_state = noop
    
    def record_llm_call(
        self,
        model: str,
        node: str,
        duration: float,
        status: str = "success",
    ):
        """记录一次LLM调用"""
        self.llm_call_duration.labels(
            model=model, node=node, status=status
        ).observe(duration)
        self.llm_call_total.labels(model=model, status=status).inc()
    
    def record_metar_analysis(
        self,
        flight_rules: str,
        risk_level: str,
    ):
        """记录一次METAR分析"""
        self.metar_analysis_total.labels(
            flight_rules=flight_rules, risk_level=risk_level
        ).inc()
    
    def record_cache_access(self, level: str, hit: bool):
        """记录缓存访问"""
        self.cache_hit_total.labels(
            cache_level=level, result="hit" if hit else "miss"
        ).inc()
    
    def record_safety_intervention(
        self,
        risk_type: str,
        action: str = "alert",
    ):
        """记录安全干预"""
        self.safety_intervention_total.labels(
            risk_type=risk_type, action=action
        ).inc()
    
    def record_workflow(self, duration: float, success: bool):
        """记录工作流完成"""
        self.workflow_duration.labels(
            success=str(success).lower()
        ).observe(duration)
    
    def record_node_execution(
        self,
        node_name: str,
        duration: float,
        status: str = "success",
    ):
        """记录节点执行"""
        self.node_duration.labels(
            node_name=node_name, status=status
        ).observe(duration)
    
    def update_circuit_breaker(self, name: str, state: str):
        """更新熔断器状态指标"""
        state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
        self.circuit_breaker_state.labels(
            breaker_name=name
        ).set(state_map.get(state, -1))


class NodeTracer:
    """
    LangGraph 节点耗时追踪器
    
    使用方式:
        tracer = NodeTracer(metrics)
        
        # 方式1: 异步上下文管理器
        async with tracer.trace("parse_metar_node"):
            result = await parse_metar(state, config)
        
        # 方式2: 装饰器
        @tracer.trace_node("generate_explanation")
        async def my_node(state, config):
            ...
    """
    
    def __init__(self, metrics: Optional[AgentMetrics] = None):
        self.metrics = metrics or get_metrics()
    
    @asynccontextmanager
    async def trace(self, node_name: str):
        """
        追踪节点执行的异步上下文管理器
        
        Yields:
            dict: 包含 start_time 和 node_name 的上下文信息
        """
        start_time = time.time()
        context = {"node_name": node_name, "start_time": start_time}
        status = "success"
        
        logger.debug(f"[trace] Node '{node_name}' started")
        
        try:
            yield context
        except Exception as e:
            status = "error"
            logger.error(f"[trace] Node '{node_name}' failed: {e}")
            raise
        finally:
            duration = time.time() - start_time
            self.metrics.record_node_execution(node_name, duration, status)
            logger.debug(
                f"[trace] Node '{node_name}' completed: "
                f"duration={duration:.3f}s, status={status}"
            )
    
    def trace_node(self, node_name: Optional[str] = None):
        """
        装饰器：追踪函数作为LangGraph节点的执行
        
        使用:
            @tracer.trace_node("my_node")
            async def my_node_func(state, config):
                ...
        """
        def decorator(func):
            name = node_name or func.__name__
            
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                async with self.trace(name):
                    return await func(*args, **kwargs)
            
            return wrapper
        return decorator


# ========== Prometheus HTTP 端点支持 ==========

def get_metrics_response() -> tuple:
    """
    获取 Prometheus 格式的指标响应
    
    Returns:
        (body, content_type) 元组，用于 FastAPI Response
    """
    if HAS_PROMETHEUS:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    else:
        return b"# prometheus_client not installed\n", "text/plain"


# ========== 全局单例 ==========

_metrics: Optional[AgentMetrics] = None
_tracer: Optional[NodeTracer] = None


def get_metrics() -> AgentMetrics:
    """获取全局指标实例"""
    global _metrics
    if _metrics is None:
        _metrics = AgentMetrics()
    return _metrics


def get_tracer() -> NodeTracer:
    """获取全局追踪器实例"""
    global _tracer
    if _tracer is None:
        _tracer = NodeTracer(get_metrics())
    return _tracer


def reset_metrics():
    """重置全局实例（用于测试）"""
    global _metrics, _tracer
    _metrics = None
    _tracer = None
