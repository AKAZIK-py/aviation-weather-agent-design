"""
FastAPI主应用入口
航空气象Agent后端服务
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import logging
import time
import json

from app.core.config import settings
from app.core.metrics import get_metrics, get_metrics_response
from app.core.telemetry import initialize_telemetry, shutdown_langfuse, shutdown_telemetry
from app.api.routes import router as api_router
from app.api.routes_v2 import router as api_router_v2
from app.api.routes_v3 import router as api_router_v3

# 配置日志
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
metrics = get_metrics()

# 创建FastAPI应用
app = FastAPI(
    title="航空气象Agent API",
    description="""
## 航空气象智能分析服务

基于大语言模型的航空气象报文分析系统，支持：
- **METAR报文解析**：自动解析标准METAR格式
- **角色识别**：识别用户角色（空管/地勤/运控/机务）
- **风险评估**：多维度风险等级评估
- **安全干预**：Critical风险自动触发人工干预
- **个性化解释**：根据角色生成定制化解释

### 技术栈
- **LLM**: 多Provider支持（百度千帆/OpenAI/Anthropic/DeepSeek/Moonshot）
- **工作流引擎**: LangGraph
- **后端框架**: FastAPI
- **评测体系**: D1-D5五维指标

### 评测指标
- D1: 规则映射准确率 ≥95%
- D2: 角色匹配准确率 ≥85%
- D3: 安全边界覆盖率 =100%
- D4: 幻觉率 ≤5%
- D5: 越权率 =0%
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=json.loads(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_request_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    start_time = time.perf_counter()
    response = None

    with metrics.track_active_request():
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            metrics.record_error("http", exc.__class__.__name__)
            raise
        finally:
            duration_seconds = time.perf_counter() - start_time
            process_time_ms = duration_seconds * 1000
            path = _resolve_request_path(request)
            status_code = response.status_code if response is not None else 500
            metrics.record_http_request(
                method=request.method,
                path=path,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            if status_code >= 500:
                metrics.record_error("http", f"status_{status_code}")

            logger.info(
                "%s %s - status=%s time=%.2fms",
                request.method,
                path,
                status_code,
                process_time_ms,
            )


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# 注册路由
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router_v2, prefix="/api/v2")
app.include_router(api_router_v3, prefix="/api/v3")  # Agent模式


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    """Prometheus 抓取端点。"""
    body, content_type = get_metrics_response()
    return Response(content=body, media_type=content_type)


# 根路径
@app.get("/", tags=["Root"])
async def root():
    """根路径 - 重定向到文档"""
    return {
        "message": "航空气象Agent API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    initialize_telemetry(app)
    logger.info(
        "Observability: metrics=%s otel=%s langfuse=%s otlp=%s",
        settings.enable_metrics,
        settings.otel_enabled,
        settings.langfuse_enabled,
        settings.otel_exporter_otlp_endpoint,
    )


# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info(f"Shutting down {settings.app_name}")
    shutdown_langfuse()
    shutdown_telemetry()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
