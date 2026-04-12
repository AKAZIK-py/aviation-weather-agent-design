"""
FastAPI主应用入口
航空气象Agent后端服务
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import json

from app.core.config import settings
from app.api.routes import router as api_router
from app.api.routes_v2 import router as api_router_v2

# 配置日志
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

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


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    start_time = time.time()
    
    # 处理请求
    response = await call_next(request)
    
    # 计算处理时间
    process_time = (time.time() - start_time) * 1000
    
    # 记录日志
    logger.info(
        f"{request.method} {request.url.path} - "
        f"status={response.status_code} time={process_time:.2f}ms"
    )
    
    return response


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


# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info(f"Shutting down {settings.app_name}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
