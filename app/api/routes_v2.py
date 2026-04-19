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

        # V2 直接走 V3 Agent（自然语言输出，非模板）
        from app.agent.graph import run_agent
        agent_result = await run_agent(
            query=user_query or f"{(user_role or '飞行员')}角色，{metar_raw}，分析天气",
            role=user_role or "pilot",
            metar_raw=metar_raw,
        )

        processing_time_ms = (time.time() - start_time) * 1000

        if not agent_result.get("success"):
            return {
                "success": False,
                "error": agent_result.get("error", "Agent 执行失败"),
                "processing_time_ms": processing_time_ms,
                "timestamp": datetime.now().isoformat(),
            }

        # Agent 输出转 V2 格式
        answer = agent_result.get("answer", "")
        metar_parsed = agent_result.get("metar_parsed", {})
        risk_level = agent_result.get("risk_level", "LOW")

        response = {
            "success": True,
            "metar_raw": metar_raw or "",
            "metar_parsed": metar_parsed,
            "metar_metadata": None,
            "detected_role": user_role or "pilot",
            "risk_level": risk_level,
            "risk_factors": agent_result.get("risk_factors", []),
            "role_report": {
                "role": user_role or "pilot",
                "risk_level": risk_level,
                "report_text": answer,
                "alerts": [],
                "model_used": agent_result.get("model_used", "deepseek"),
                "generated_at": datetime.now().isoformat(),
            },
            "explanation": answer,
            "structured_analysis": None,
            "llm_calls": agent_result.get("iterations", 0),
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
