"""
OpenTelemetry 与 Langfuse 集成助手。

设计目标：
- 应用链路通过 OTel -> Collector -> Phoenix
- LangChain/LangGraph 通过 Langfuse CallbackHandler 记录 LLM 语义追踪
- 缺少依赖时自动降级，不阻塞主业务
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 依赖存在时运行
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    HAS_OTEL = True
except ImportError:  # pragma: no cover - 依赖缺失时降级
    HAS_OTEL = False
    trace = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]

try:  # pragma: no cover - 依赖存在时运行
    from langfuse import Langfuse, get_client, propagate_attributes
    from langfuse.langchain import CallbackHandler

    HAS_LANGFUSE = True
except ImportError:  # pragma: no cover - 依赖缺失时降级
    HAS_LANGFUSE = False
    Langfuse = None  # type: ignore[assignment]
    CallbackHandler = None  # type: ignore[assignment]
    get_client = None  # type: ignore[assignment]
    propagate_attributes = None  # type: ignore[assignment]


class _NoOpSpan:
    def set_attribute(self, *args, **kwargs):
        return None

    def record_exception(self, *args, **kwargs):
        return None

    def set_status(self, *args, **kwargs):
        return None


class _NoOpSpanContext:
    def __enter__(self):
        return _NoOpSpan()

    def __exit__(self, exc_type, exc, tb):
        return False


class _NoOpTracer:
    def start_as_current_span(self, *args, **kwargs):
        return _NoOpSpanContext()


_OTEL_LOCK = Lock()
_OTEL_INITIALIZED = False
_OTEL_PROVIDER: Optional["TracerProvider"] = None
_AIOHTTP_INSTRUMENTED = False

_LANGFUSE_LOCK = Lock()
_LANGFUSE_INITIALIZED = False
_LANGFUSE_ENABLED = False


def _normalize_otlp_endpoint(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return f"{endpoint}/v1/traces"


def initialize_telemetry(app=None) -> bool:
    """初始化 OTel tracing 与自动埋点。"""
    global _OTEL_INITIALIZED, _OTEL_PROVIDER, _AIOHTTP_INSTRUMENTED

    settings = get_settings()
    if not settings.enable_observability or not settings.otel_enabled:
        return False

    if not HAS_OTEL:
        logger.warning("OpenTelemetry 依赖未安装，跳过 tracing 初始化")
        return False

    with _OTEL_LOCK:
        if not _OTEL_INITIALIZED:
            resource = Resource.create(
                {
                    "service.name": settings.otel_service_name,
                    "service.namespace": settings.otel_service_namespace,
                    "service.version": settings.app_version,
                    "deployment.environment": settings.otel_environment,
                    # Phoenix / OpenInference 用于项目分组
                    "openinference.project.name": settings.phoenix_project_name,
                }
            )

            provider = TracerProvider(resource=resource)
            provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=_normalize_otlp_endpoint(
                            settings.otel_exporter_otlp_endpoint
                        ),
                        timeout=settings.otel_export_timeout_ms,
                    )
                )
            )
            trace.set_tracer_provider(provider)
            _OTEL_PROVIDER = provider
            _OTEL_INITIALIZED = True
            logger.info(
                "OpenTelemetry 已初始化，OTLP endpoint=%s",
                settings.otel_exporter_otlp_endpoint,
            )

        if app is not None:
            try:
                FastAPIInstrumentor.instrument_app(
                    app,
                    tracer_provider=_OTEL_PROVIDER,
                    excluded_urls=settings.otel_excluded_urls,
                )
            except Exception as exc:  # pragma: no cover - 第三方库幂等行为
                logger.debug("FastAPI instrumentation 跳过: %s", exc)

        if not _AIOHTTP_INSTRUMENTED:
            try:
                AioHttpClientInstrumentor().instrument(tracer_provider=_OTEL_PROVIDER)
                _AIOHTTP_INSTRUMENTED = True
            except Exception as exc:  # pragma: no cover - 第三方库幂等行为
                logger.debug("aiohttp instrumentation 跳过: %s", exc)

    return True


def shutdown_telemetry() -> None:
    global _OTEL_PROVIDER
    if _OTEL_PROVIDER is not None:
        try:
            _OTEL_PROVIDER.shutdown()
        except Exception as exc:  # pragma: no cover
            logger.debug("OTel provider shutdown 失败: %s", exc)


def get_tracer(name: str):
    if not HAS_OTEL:
        return _NoOpTracer()
    return trace.get_tracer(name)


def mark_span_error(span, error: Optional[BaseException] = None, message: Optional[str] = None) -> None:
    if span is None:
        return

    error_message = message or (str(error) if error else "unknown error")
    if error is not None and hasattr(span, "record_exception"):
        span.record_exception(error)

    if HAS_OTEL and hasattr(span, "set_status"):
        span.set_status(Status(StatusCode.ERROR, error_message))


def _ensure_langfuse_client() -> bool:
    """按需初始化 Langfuse singleton client。"""
    global _LANGFUSE_INITIALIZED, _LANGFUSE_ENABLED

    settings = get_settings()
    if not settings.enable_observability or not settings.langfuse_enabled:
        return False

    if not HAS_LANGFUSE:
        logger.warning("langfuse 依赖未安装，跳过 Langfuse tracing")
        return False

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 未配置，跳过 Langfuse tracing")
        return False

    with _LANGFUSE_LOCK:
        if not _LANGFUSE_INITIALIZED:
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
            )
            _LANGFUSE_INITIALIZED = True
            _LANGFUSE_ENABLED = True
            logger.info("Langfuse 已初始化，base_url=%s", settings.langfuse_base_url)

    return _LANGFUSE_ENABLED


@contextmanager
def langfuse_trace_context(
    *,
    trace_name: str,
    role: str,
    provider: str,
    session_id: Optional[str],
    user_id: Optional[str],
):
    """
    为单次 agent 运行创建 Langfuse handler 与 trace attributes。
    """
    if not _ensure_langfuse_client():
        yield None
        return

    tags = [
        "aviation-weather-agent",
        f"role:{role}",
        f"provider:{provider}",
    ]

    handler = CallbackHandler()
    with propagate_attributes(
        trace_name=trace_name,
        session_id=session_id or "anonymous-session",
        user_id=user_id or "anonymous-user",
        tags=tags,
    ):
        yield handler


def get_langfuse_trace_info(handler) -> dict:
    """返回 trace_id / trace_url，便于写入响应和日志。"""
    if handler is None or not HAS_LANGFUSE:
        return {}

    trace_id = getattr(handler, "last_trace_id", None)
    if not trace_id:
        return {}

    info = {"langfuse_trace_id": trace_id}
    try:
        info["langfuse_trace_url"] = get_client().get_trace_url(trace_id=trace_id)
    except Exception as exc:  # pragma: no cover
        logger.debug("获取 Langfuse trace url 失败: %s", exc)
    return info


def shutdown_langfuse() -> None:
    if not HAS_LANGFUSE or not _LANGFUSE_INITIALIZED:
        return
    try:
        get_client().flush()
    except Exception as exc:  # pragma: no cover
        logger.debug("Langfuse flush 失败: %s", exc)
