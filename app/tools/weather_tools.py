"""
航空气象工具集 - 将现有服务包装为 LLM 可调用的 Tool

每个工具：
- 输入：结构化参数（Pydantic model）
- 输出：结构化 dict（JSON可序列化）
- 失败：返回 {"error": "具体错误信息"} 而非抛异常
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.nodes.parse_metar_node import parse_metar_node
from app.nodes.assess_risk_node import assess_risk_node
from app.utils.visibility import format_visibility_range
from app.utils.approach import format_decision_info

logger = logging.getLogger(__name__)


# ==================== Tool Schema 定义 ====================

class FetchMetarParams(BaseModel):
    """获取指定ICAO机场的实时METAR报文"""
    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


class ParseMetarParams(BaseModel):
    """解析原始METAR报文为结构化数据，包含飞行规则、风、能见度、云层等"""
    raw_metar: str = Field(description="原始METAR报文文本")


class GetFlightRulesParams(BaseModel):
    """根据能见度和云底高计算ICAO Annex 3飞行规则"""
    visibility_km: float = Field(description="能见度，单位千米")
    ceiling_ft: Optional[float] = Field(
        default=None,
        description="云底高（最低BKN/OVC层），单位英尺。FEW和SCT不算ceiling。无云底时传null"
    )


class AssessRiskParams(BaseModel):
    """多维度风险评估：能见度、风、天气现象、风切变、云底高"""
    metar_parsed: Dict[str, Any] = Field(description="parse_metar工具返回的结构化METAR数据")


class GetApproachMinimaParams(BaseModel):
    """获取机场指定跑道的进近最低标准（DH/MDA）"""
    icao: str = Field(description="4字母ICAO机场代码")
    runway: Optional[str] = Field(default=None, description="跑道号，如 '01'、'19L'。不指定则返回所有跑道")


class FormatVisibilityParams(BaseModel):
    """将能见度精确值转换为区间化描述（对外展示用）"""
    visibility_km: float = Field(description="能见度精确值，单位千米")


class FetchTafParams(BaseModel):
    """获取指定ICAO机场的TAF预报报文"""
    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


class GetFullWeatherParams(BaseModel):
    """获取机场完整气象信息（METAR实况 + TAF预报），联合分析用"""
    icao: str = Field(description="4字母ICAO机场代码，如 ZBAA、ZSPD")


# ==================== Tool 执行函数 ====================

async def _fetch_metar(params: FetchMetarParams) -> Dict[str, Any]:
    """获取实时METAR"""
    from app.services.metar_fetcher import fetch_metar_for_airport, MetarFetchError
    try:
        raw_metar, metadata = await fetch_metar_for_airport(params.icao)
        return {
            "icao": params.icao.upper(),
            "raw_metar": raw_metar,
            "metadata": metadata,
        }
    except MetarFetchError as e:
        return {"error": f"获取{params.icao}的METAR失败: {str(e)}"}
    except Exception as e:
        return {"error": f"网络或服务异常: {str(e)}"}


async def _parse_metar(params: ParseMetarParams) -> Dict[str, Any]:
    """解析METAR报文"""
    try:
        state = {"metar_raw": params.raw_metar}
        result = await parse_metar_node(state, None)
        if result.get("parse_error"):
            return {"error": f"解析失败: {result['parse_error']}"}
        return {
            "metar_parsed": result.get("metar_parsed", {}),
            "parse_success": result.get("parse_success", False),
        }
    except Exception as e:
        return {"error": f"METAR解析异常: {str(e)}"}


async def _get_flight_rules(params: GetFlightRulesParams) -> Dict[str, Any]:
    """计算飞行规则"""
    vis_sm = params.visibility_km / 1.60934
    ceiling_ft = params.ceiling_ft

    # ICAO Annex 3 标准
    # 取能见度和ceiling中较差的类别
    def _vis_category(v_sm):
        if v_sm < 1:
            return "LIFR"
        elif v_sm < 3:
            return "IFR"
        elif v_sm < 5:
            return "MVFR"
        else:
            return "VFR"

    def _ceil_category(c_ft):
        if c_ft is None:
            return "VFR"
        elif c_ft < 500:
            return "LIFR"
        elif c_ft < 1000:
            return "IFR"
        elif c_ft < 3000:
            return "MVFR"
        else:
            return "VFR"

    cats = [_vis_category(vis_sm)]
    if ceiling_ft is not None:
        cats.append(_ceil_category(ceiling_ft))

    order = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}
    worst = min(cats, key=lambda c: order.get(c, 3))

    return {
        "flight_rules": worst,
        "visibility_sm": round(vis_sm, 2),
        "ceiling_ft": ceiling_ft,
        "visibility_category": _vis_category(vis_sm),
        "ceiling_category": _ceil_category(ceiling_ft) if ceiling_ft else None,
    }


async def _assess_risk(params: AssessRiskParams) -> Dict[str, Any]:
    """风险评估"""
    try:
        state = {"metar_parsed": params.metar_parsed}
        result = await assess_risk_node(state, None)
        return {
            "risk_level": result.get("risk_level", "LOW"),
            "risk_factors": result.get("risk_factors", []),
            "risk_reasoning": result.get("risk_reasoning", ""),
        }
    except Exception as e:
        return {"error": f"风险评估异常: {str(e)}"}


async def _get_approach_minima(params: GetApproachMinimaParams) -> Dict[str, Any]:
    """获取进近最低标准"""
    try:
        info = format_decision_info(params.icao, params.runway)
        return {
            "icao": params.icao.upper(),
            "runway": params.runway,
            "approach_minima": info,
        }
    except Exception as e:
        return {"error": f"获取进近标准失败: {str(e)}"}


async def _format_visibility(params: FormatVisibilityParams) -> Dict[str, Any]:
    """能见度区间化"""
    range_str = format_visibility_range(params.visibility_km)
    return {
        "exact_km": params.visibility_km,
        "range_description": range_str,
    }


async def _fetch_taf(params: FetchTafParams) -> Dict[str, Any]:
    """获取TAF预报"""
    from app.services.metar_fetcher import fetch_taf_for_airport, MetarFetchError
    try:
        raw_taf, metadata = await fetch_taf_for_airport(params.icao)
        return {
            "icao": params.icao.upper(),
            "raw_taf": raw_taf,
            "metadata": metadata,
        }
    except MetarFetchError as e:
        return {"error": f"获取{params.icao}的TAF失败: {str(e)}"}
    except Exception as e:
        return {"error": f"网络或服务异常: {str(e)}"}


async def _get_full_weather(params: GetFullWeatherParams) -> Dict[str, Any]:
    """获取METAR+TAF联合数据"""
    from app.services.metar_fetcher import (
        fetch_metar_for_airport,
        fetch_taf_for_airport,
        MetarFetchError,
    )
    icao = params.icao.upper()
    result = {"icao": icao}

    # 获取METAR
    try:
        raw_metar, metar_meta = await fetch_metar_for_airport(icao)
        result["metar"] = {"raw": raw_metar, "metadata": metar_meta}
    except MetarFetchError as e:
        result["metar"] = {"error": str(e)}
    except Exception as e:
        result["metar"] = {"error": f"网络异常: {str(e)}"}

    # 获取TAF
    try:
        raw_taf, taf_meta = await fetch_taf_for_airport(icao)
        result["taf"] = {"raw": raw_taf, "metadata": taf_meta}
    except MetarFetchError as e:
        result["taf"] = {"error": str(e)}
    except Exception as e:
        result["taf"] = {"error": f"网络异常: {str(e)}"}

    return result


# ==================== Tool 注册表 ====================

TOOL_REGISTRY = {
    "fetch_metar": {
        "function": _fetch_metar,
        "schema": FetchMetarParams,
        "description": "获取指定ICAO机场的实时METAR报文。输入4字母机场代码，返回原始METAR文本和元数据。",
    },
    "parse_metar": {
        "function": _parse_metar,
        "schema": ParseMetarParams,
        "description": "解析原始METAR报文为结构化数据。包含飞行规则、风向风速、能见度、云层、温度、天气现象等。",
    },
    "get_flight_rules": {
        "function": _get_flight_rules,
        "schema": GetFlightRulesParams,
        "description": "根据能见度(km)和云底高(ft)计算ICAO Annex 3飞行规则(VFR/MVFR/IFR/LIFR)。FEW/SCT不算ceiling。",
    },
    "assess_risk": {
        "function": _assess_risk,
        "schema": AssessRiskParams,
        "description": "多维度风险评估。检查危险天气、风切变、低能见度(<1km=CRITICAL)、低云底高、强风等。",
    },
    "get_approach_minima": {
        "function": _get_approach_minima,
        "schema": GetApproachMinimaParams,
        "description": "获取机场指定跑道的进近最低标准(DH/MDA)。包含ILS CAT I/II/III和VOR进近。",
    },
    "format_visibility": {
        "function": _format_visibility,
        "schema": FormatVisibilityParams,
        "description": "将能见度精确值转换为区间化描述(如'6-10km')。对外展示用，避免暴露精确值。",
    },
    "fetch_taf": {
        "function": _fetch_taf,
        "schema": FetchTafParams,
        "description": "获取指定ICAO机场的TAF预报报文。返回原始TAF文本和结构化预报数据（各时段风、能见度、天气、云层）。",
    },
    "get_full_weather": {
        "function": _get_full_weather,
        "schema": GetFullWeatherParams,
        "description": "一次获取机场的METAR实况+TAF预报。适合需要联合分析当前天气和未来趋势的场景。METAR和TAF任一获取失败不会阻断另一个。",
    },
}


def get_all_tools() -> List[Dict[str, Any]]:
    """
    获取所有工具定义，适配 LangChain Tool 格式
    """
    from langchain_core.tools import StructuredTool

    tools = []
    for name, info in TOOL_REGISTRY.items():
        tool = StructuredTool(
            name=name,
            description=info["description"],
            args_schema=info["schema"],
            coroutine=info["function"],
            handle_tool_error=True,
        )
        tools.append(tool)

    return tools
