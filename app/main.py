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
from app.api.routes_system import router as system_router

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
app.include_router(system_router, prefix="/api/v3")  # 系统端点


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    """Prometheus 抓取端点。"""
    body, content_type = get_metrics_response()
    return Response(content=body, media_type=content_type)


# 根路径
@app.get("/", tags=["Root"])
async def root():
    """系统概览 — 实时运行 Dashboard"""
    from app.services.live_metrics import get_live_status
    from fastapi.responses import HTMLResponse

    data = get_live_status()
    totals = data["totals"]
    recent = data["recent_1h"]
    providers = data["providers"]
    last_reqs = data["last_requests"]
    obs = data["observability"]

    # 最近请求表格行
    req_rows = ""
    for r in last_reqs:
        color = "#22c55e" if r["status"] == "success" else "#ef4444"
        req_rows += f"""<tr>
            <td>{r['time_short']}</td>
            <td>{r['role']}</td>
            <td>{r['provider']}/{r['model']}</td>
            <td style="color:{color}">{r['status']}</td>
            <td>{r['latency_ms']:.0f}ms</td>
            <td>{r['prompt_tokens']}</td>
            <td>{r['completion_tokens']}</td>
            <td><b>{r['total_tokens']}</b></td>
            <td>{r['query'][:40]}</td>
        </tr>"""

    # Provider 表格行
    prov_rows = ""
    for p in providers:
        err_color = "#ef4444" if p["error_rate"] > 0.1 else "#22c55e"
        prov_rows += f"""<tr>
            <td>{p['provider']}</td>
            <td>{p['requests']}</td>
            <td>{p['tokens']:,}</td>
            <td style="color:{err_color}">{p['error_rate']:.1%}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>航空气象Agent — 控制台</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
  h1 {{ font-size:24px; margin-bottom:4px; }}
  .subtitle {{ color:#94a3b8; font-size:14px; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px; }}
  .card {{ background:#1e293b; border-radius:12px; padding:20px; }}
  .card-title {{ color:#94a3b8; font-size:12px; text-transform:uppercase; letter-spacing:1px; }}
  .card-value {{ font-size:32px; font-weight:700; margin:8px 0; }}
  .card-sub {{ color:#64748b; font-size:12px; }}
  .green {{ color:#22c55e; }} .yellow {{ color:#eab308; }} .red {{ color:#ef4444; }} .cyan {{ color:#06b6d4; }}
  .section {{ background:#1e293b; border-radius:12px; padding:20px; margin-bottom:24px; }}
  .section h2 {{ font-size:16px; margin-bottom:16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ text-align:left; color:#94a3b8; padding:8px 12px; border-bottom:1px solid #334155; font-weight:500; }}
  td {{ padding:8px 12px; border-bottom:1px solid #1e293b; }}
  tr:hover {{ background:#334155; }}
  .links {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .link {{ display:inline-flex; align-items:center; gap:6px; background:#334155; padding:8px 16px;
           border-radius:8px; color:#93c5fd; text-decoration:none; font-size:13px; transition:background 0.2s; }}
  .link:hover {{ background:#475569; }}
  .ring {{ width:80px; height:80px; }}
  .ring circle {{ fill:none; stroke-width:8; }}
  .ring .bg {{ stroke:#334155; }}
  .ring .fg {{ stroke-linecap:round; transition:stroke-dashoffset 0.6s; }}
  .top-row {{ display:flex; gap:16px; align-items:stretch; }}
  .top-row .card {{ flex:1; display:flex; align-items:center; gap:16px; }}
</style>
</head>
<body>
<h1>✈️ 航空气象Agent 控制台</h1>
<p class="subtitle">ReAct Agent (LangGraph) · {data['version']} · {data['uptime_check'][:19]}</p>

<div class="grid">
  <div class="card">
    <div class="card-title">总请求</div>
    <div class="card-value cyan">{totals['requests']}</div>
    <div class="card-sub">成功率 <span class="{'green' if totals['success_rate']>0.9 else 'yellow' if totals['success_rate']>0.7 else 'red'}">{totals['success_rate']:.0%}</span></div>
  </div>
  <div class="card">
    <div class="card-title">总 Token 消耗</div>
    <div class="card-value yellow">{totals['total_tokens']:,}</div>
    <div class="card-sub">输入 {totals['prompt_tokens']:,} · 输出 {totals['completion_tokens']:,}</div>
  </div>
  <div class="card">
    <div class="card-title">近1h 平均延迟</div>
    <div class="card-value">{recent['avg_latency_ms']:.0f}<span style="font-size:14px;color:#94a3b8">ms</span></div>
    <div class="card-sub">P95 {recent['p95_latency_ms']:.0f}ms · {recent['requests']} 次请求</div>
  </div>
  <div class="card">
    <div class="card-title">错误</div>
    <div class="card-value {'red' if totals['errors']>0 else 'green'}">{totals['errors']}</div>
    <div class="card-sub">共 {totals['requests']} 次请求</div>
  </div>
</div>

<div class="section">
  <h2>📊 Provider 统计</h2>
  <table>
    <tr><th>Provider / Model</th><th>请求次数</th><th>Token 消耗</th><th>错误率</th></tr>
    {prov_rows if prov_rows else '<tr><td colspan="4" style="color:#64748b">暂无数据</td></tr>'}
  </table>
</div>

<div class="section">
  <h2>📋 最近请求 Trace</h2>
  <table>
    <tr><th>时间</th><th>角色</th><th>Provider</th><th>状态</th><th>延迟</th><th>输入Token</th><th>输出Token</th><th>总Token</th><th>查询</th></tr>
    {req_rows if req_rows else '<tr><td colspan="9" style="color:#64748b">暂无请求记录</td></tr>'}
  </table>
</div>

<div class="section">
  <h2>🔗 可观测性</h2>
  <div class="links">
    <a class="link" href="{obs['langfuse']}" target="_blank">🔍 Langfuse — Trace 追踪 / Prompt 调试</a>
    <a class="link" href="{obs['grafana']}" target="_blank">📈 Grafana — 监控 Dashboard</a>
    <a class="link" href="{obs['prometheus_metrics']}" target="_blank">📊 Prometheus — 原始指标</a>
    <a class="link" href="/docs" target="_blank">📖 Swagger API 文档</a>
  </div>
</div>

<script>
// 每30秒自动刷新
setTimeout(() => location.reload(), 30000);
</script>
</body></html>"""

    return HTMLResponse(content=html)


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
