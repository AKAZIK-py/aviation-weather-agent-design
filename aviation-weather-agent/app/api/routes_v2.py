"""
V2 API路由 - 增强版天气分析端点
返回包含 role_report 的完整工作流结果
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import time
import logging
from typing import Optional

from app.services.workflow_engine import get_workflow_engine
from app.api.schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze")
async def analyze_weather_v2(request: dict):
    """
    V2 增强版天气分析端点

    支持两种输入方式:
    1. { "airport_icao": "ZSPD", "user_role": "pilot" }  - 通过ICAO获取实时METAR
    2. { "metar_raw": "METAR ...", "user_role": "pilot" } - 直接输入METAR

    Returns:
        包含 role_report 的完整分析结果
    """
    start_time = time.time()

    try:
        airport_icao = request.get("airport_icao")
        metar_raw = request.get("metar_raw")
        user_role = request.get("user_role") or request.get("role")
        user_query = request.get("user_query", "")

        if not airport_icao and not metar_raw:
            raise HTTPException(
                status_code=400,
                detail="必须提供 airport_icao 或 metar_raw 参数"
            )

        # 运行完整工作流
        engine = get_workflow_engine()
        result = await engine.run_full_workflow(
            airport_icao=airport_icao,
            metar_raw=metar_raw,
            user_query=user_query,
            user_role=user_role,
        )

        processing_time_ms = (time.time() - start_time) * 1000

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "未知错误"),
                "processing_time_ms": processing_time_ms,
                "timestamp": datetime.now().isoformat(),
            }

        metar_parsed = result.get("metar_parsed", {})

        # 构建 V2 响应
        response = {
            "success": True,
            "metar_raw": result.get("raw_metar", metar_raw),
            "metar_parsed": metar_parsed,
            "metar_metadata": result.get("metar_metadata"),
            "detected_role": result.get("detected_role"),
            "risk_level": result.get("risk_level"),
            "risk_factors": result.get("risk_factors", []),
            "role_report": result.get("role_report"),
            "explanation": result.get("explanation"),
            "structured_analysis": result.get("structured_analysis"),
            "llm_calls": result.get("llm_calls", 0),
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"V2 analyze completed: role={response['detected_role']}, "
            f"risk={response['risk_level']}, time={processing_time_ms:.2f}ms, "
            f"has_role_report={response['role_report'] is not None}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"V2 analyze failed: {e}", exc_info=True)
        processing_time_ms = (time.time() - start_time) * 1000
        return {
            "success": False,
            "error": str(e),
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/airports/{icao}/metar")
async def get_airport_metar(icao: str):
    """获取指定机场的METAR数据"""
    engine = get_workflow_engine()
    result = await engine.get_metar_for_airport(icao)
    return result


@router.get("/airports/{icao}/report/{role}")
async def get_role_report(icao: str, role: str):
    """获取指定机场和角色的专属报告"""
    valid_roles = ["pilot", "dispatcher", "forecaster", "ground_crew"]
    if role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"无效角色: {role}，可选: {valid_roles}"
        )

    engine = get_workflow_engine()
    result = await engine.get_role_specific_report(icao, role)
    return result
