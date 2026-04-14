"""
API路由 - 天气分析端点
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import time
import logging
from typing import List, Dict

from app.api.schemas import (
    WeatherAnalyzeRequest,
    WeatherAnalyzeResponse,
    HealthCheckResponse,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from app.core.workflow import run_workflow
from app.core.llm_client import get_llm_client
from app.services.metar_fetcher import fetch_metar_for_airport, MetarFetchError, is_airport_supported
from app.data.airports import JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analyze",
    response_model=WeatherAnalyzeResponse,
    summary="分析METAR天气报文",
    description="接收METAR报文或机场ICAO代码，返回个性化的天气分析和风险提示",
    responses={
        200: {"description": "分析成功"},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    }
)
async def analyze_weather(
    request: WeatherAnalyzeRequest,
    req: Request,
):
    """
    分析METAR天气报文
    
    工作流程：
    1. 获取METAR报文（直接输入或从机场ICAO获取实时数据）
    2. 解析METAR报文 → 结构化数据
    3. 识别用户角色 → 空管/地勤/运控/机务
    4. 评估风险等级 → LOW/MEDIUM/HIGH/CRITICAL
    5. 检查安全边界 → 触发干预或继续
    6. 生成个性化解释 → 自然语言输出
    
    D1-D5评测指标：
    - D1: 规则映射准确率 ≥95%
    - D2: 角色匹配准确率 ≥85%
    - D3: 安全边界覆盖率 =100%
    - D4: 幻觉率 ≤5%
    - D5: 越权率 =0%
    """
    start_time = time.time()
    metar_metadata = None
    
    try:
        # 验证请求参数
        is_valid, error_msg = request.validate_request()
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # 获取METAR报文
        if request.airport_icao:
            # 从机场ICAO代码获取实时METAR
            icao = request.airport_icao.upper()
            
            # 检查是否支持该机场（仅警告，不阻断）
            if not is_airport_supported(icao):
                logger.warning(f"Airport {icao} not in supported list, but will try to fetch anyway")
            
            logger.info(f"Fetching live METAR for airport: {icao}")
            
            try:
                metar_raw, metar_metadata = await fetch_metar_for_airport(icao)
                logger.info(f"Successfully fetched METAR: {metar_raw[:50]}...")
            except MetarFetchError as e:
                raise HTTPException(status_code=503, detail=f"无法获取机场 {icao} 的实时METAR数据: {str(e)}")
        else:
            # 使用直接输入的METAR报文
            metar_raw = request.metar_raw
        
        logger.info(f"Processing request: session={request.session_id}, metar={metar_raw[:30]}...")
        
        # 运行工作流
        result = await run_workflow(
            metar_raw=metar_raw,
            user_query=request.user_query or "",
            user_role=request.role,
            session_id=request.session_id,
        )
        
        # 计算处理时间
        processing_time_ms = (time.time() - start_time) * 1000
        
        # 构建响应
        response = WeatherAnalyzeResponse(
            success=True,
            metar_parsed=result.get("metar_parsed"),
            detected_role=result.get("detected_role"),
            risk_level=result.get("risk_level"),
            risk_factors=result.get("risk_factors", []),
            explanation=result.get("explanation"),
            intervention_required=result.get("intervention_required", False),
            intervention_reason=result.get("intervention_reason"),
            reasoning_trace=result.get("reasoning_trace", []),
            llm_calls=result.get("llm_calls", 0),
            processing_time_ms=processing_time_ms,
            metar_metadata=metar_metadata,  # 添加元数据
        )
        
        logger.info(f"Request completed: role={response.detected_role}, risk={response.risk_level}, time={processing_time_ms:.2f}ms")
        
        return response
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return WeatherAnalyzeResponse(
            success=False,
            error=str(e),
            processing_time_ms=processing_time_ms,
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="健康检查",
    description="检查服务运行状态和LLM连接",
)
async def health_check():
    """
    健康检查端点
    
    返回：
    - 服务状态
    - 版本信息
    - LLM可用性
    """
    try:
        # 检查LLM客户端
        llm_client = get_llm_client()  # 不是async函数，不需要await
        # 检查当前provider是否已配置
        current_provider = llm_client.get_current_provider()
        available_providers = llm_client.get_available_providers()
        llm_available = current_provider in available_providers and len(available_providers) > 0
        logger.info(f"Health check: provider={current_provider}, available={available_providers}")
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        llm_available = False
    
    return HealthCheckResponse(
        status="healthy" if llm_available else "degraded",
        version="1.0.0",
        llm_available=llm_available,
    )


@router.get(
    "/airports",
    summary="获取机场列表",
    description="返回江浙沪地区支持的机场列表",
)
async def get_airports():
    """
    获取江浙沪机场列表
    
    返回所有支持的机场信息，包括ICAO、IATA代码、名称、城市等
    """
    airports_list = [
        {
            "icao": airport.icao,
            "name": airport.name_cn,
            "city": airport.city_cn,
            "iata": airport.iata
        }
        for airport in JANGSU_ZHEJIANG_SHANGHAI_AIRPORTS
    ]
    
    return {
        "airports": airports_list
    }


@router.get(
    "/metrics",
    summary="服务指标",
    description="返回服务运行指标（用于监控）",
)
async def get_metrics():
    """
    服务指标端点
    
    Prometheus格式指标：
    - 请求总数
    - 平均处理时间
    - LLM调用次数
    - 错误率
    """
    # TODO: 实现实际的指标收集
    return JSONResponse(
        content={
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "avg_processing_time_ms": 0,
            "llm_calls_total": 0,
        }
    )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="提交用户反馈",
    description="提交对天气分析结果的用户反馈",
    responses={
        200: {"description": "反馈提交成功"},
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    }
)
async def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈
    
    允许用户对天气分析结果进行评分和更正：
    - rating: 评分 (1-5)
    - corrections: 更正数据，用于改进系统
    - safety_issue: 标记安全问题，会触发特殊处理
    - comment: 用户评论
    
    反馈将用于：
    1. 系统质量监控
    2. 安全问题追踪
    3. 模型改进数据收集
    """
    try:
        from app.services.feedback import get_feedback_service
        
        feedback_service = get_feedback_service()
        
        # 提交反馈
        result = feedback_service.submit_feedback(
            session_id=request.session_id,
            rating=request.rating,
            report_id=request.report_id,
            corrections=request.corrections,
            safety_issue=request.safety_issue,
            comment=request.comment
        )
        
        logger.info(f"Feedback submitted: {result['feedback_id']}, rating: {request.rating}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=result["feedback_id"],
            message=result["message"],
            timestamp=datetime.fromisoformat(result["timestamp"])
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=f"反馈提交失败: {str(e)}")


@router.get(
    "/feedback/stats",
    summary="获取反馈统计",
    description="获取用户反馈的统计信息"
)
async def get_feedback_stats():
    """
    获取反馈统计信息
    
    返回：
    - 总反馈数
    - 平均评分
    - 评分分布
    - 安全问题数量
    - 更正数量
    - 最近24小时反馈数
    """
    try:
        from app.services.feedback import get_feedback_service
        
        feedback_service = get_feedback_service()
        stats = feedback_service.get_feedback_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"获取反馈统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取反馈统计失败: {str(e)}")


@router.get(
    "/feedback/safety-issues",
    summary="获取安全问题列表",
    description="获取标记为安全问题的反馈列表"
)
async def get_safety_issues(limit: int = 50):
    """
    获取安全问题列表
    
    Args:
        limit: 返回的最大数量，默认50
    
    Returns:
        安全问题反馈列表
    """
    try:
        from app.services.feedback import get_feedback_service
        
        feedback_service = get_feedback_service()
        issues = feedback_service.get_safety_issues(limit=limit)
        
        return {
            "success": True,
            "safety_issues": issues,
            "count": len(issues)
        }
        
    except Exception as e:
        logger.error(f"获取安全问题失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取安全问题失败: {str(e)}")
